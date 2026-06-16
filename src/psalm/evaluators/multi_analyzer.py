import warnings
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from scipy.stats import kruskal, mannwhitneyu, ttest_ind
from statsmodels.stats.multitest import multipletests

warnings.filterwarnings("ignore")

plt.style.use("seaborn-v0_8-darkgrid")
sns.set_palette("husl")


class MultiModelUnlearningAnalyzer:
    """
    Multi-model comparator for unlearning evaluations.

    - Ingests multiple CSV/Parquet result files with the same schema as used by UnlearningAnalyzer
    - Computes per-metric cross-model comparisons (forget vs retain aware)
    - Provides omnibus tests (Kruskal–Wallis by default) and pairwise post-hoc tests with
      multiple testing correction (Holm-Bonferroni default)
    - Aggregates by metric categories (memorization, stylometry, content, copyright)
    - Exports publication-ready tables and figures

    Usage:
        comparator = MultiModelUnlearningAnalyzer(
            files={
                "ModelA": "path/to/a.csv",
                "ModelB": "path/to/b.parquet",
                "ModelC": "path/to/c.csv",
                "ModelD": "path/to/d.csv",
            }
        )
        comparator.run_full_comparison(out_dir="mmu_outputs", analyze_split="both")
    """

    def __init__(
        self,
        files: Dict[str, Union[str, Path]],
        metric_categories: Optional[Dict[str, List[str]]] = None,
        required_base_cols: Optional[Sequence[str]] = None,
        alpha: float = 0.05,
        correction: str = "holm",  # multipletests: 'holm', 'fdr_bh', etc.
        prefer_nonparametric: bool = True,
        verbose: bool = True,
    ):
        self.files = {k: Path(v) for k, v in files.items()}
        self.model_names = list(self.files.keys())
        self.alpha = alpha
        self.correction = correction
        self.prefer_nonparametric = prefer_nonparametric
        self.verbose = verbose

        # Default categories consistent with your single-model analyzer
        if metric_categories is None:
            self.metric_categories = {
                "Computational": ["Exact Match_score", "BLEU_score", "ROUGE_score"],
                "Stylistic": ["Writing Style_score", "Narrative Voice_score"],
                "Content": [
                    "Character Similarity_score",
                    "Plot Structure Similarity_score",
                    "Scene Sequence Similarity_score",
                    "WorldBuilding Similarity_score",
                ],
                "Exceptions": [
                    "Parody/Satire_score",
                    "Pastiche_score",
                    "Quotation/Citation_score",
                    "Scènes à Faire_score",
                ],
            }
        else:
            self.metric_categories = metric_categories

        # Base columns the per-file data must have
        if required_base_cols is None:
            self.required_base_cols = [
                "ti_id",
                "author",
                "is_forget",
                "question",
                "expected_answer",
                "actual_answer",
            ]
        else:
            self.required_base_cols = list(required_base_cols)

        # Flatten metrics
        self.all_metrics = []
        for mlist in self.metric_categories.values():
            self.all_metrics.extend(mlist)
        self.all_metrics = list(dict.fromkeys(self.all_metrics))  # unique preserve order

        # Storage
        self.data_long = None
        self.per_metric_stats = None
        self.per_category_stats = None
        self.ranks_df = None
        self.posthoc_df = None

        self._load_and_harmonize()

    def _load_and_harmonize(self):
        frames = []
        for model, path in self.files.items():
            if path.suffix == ".csv":
                df = pd.read_csv(path)
            elif path.suffix == ".parquet":
                df = pd.read_parquet(path)
            else:
                raise NotImplementedError(f"Unsupported file type: {path}")

            # Validate
            missing_cols = [c for c in self.required_base_cols if c not in df.columns]
            missing_metrics = [m for m in self.all_metrics if m not in df.columns]
            if missing_cols:
                raise ValueError(
                    f"Model '{model}': missing required columns: {missing_cols}"
                )
            if missing_metrics:
                if self.verbose:
                    print(
                        f"[WARN] Model '{model}' missing metrics: {missing_metrics}. "
                        f"These will be excluded for this model."
                    )

            # Keep only required + available metrics
            keep_cols = self.required_base_cols + [m for m in self.all_metrics if m in df.columns]
            dfx = df[keep_cols].copy()
            dfx["model"] = model
            frames.append(dfx)

        combined = pd.concat(frames, ignore_index=True)
        # Melt to long format for ease of groupby and plotting
        long = combined.melt(
            id_vars=self.required_base_cols + ["model"],
            value_vars=[m for m in self.all_metrics if m in combined.columns],
            var_name="metric",
            value_name="score",
        )
        # Clean metric names for presentation
        long["metric_clean"] = long["metric"].str.replace("_score", "", regex=False)

        # Attach category
        metric_to_cat = {}
        for cat, mlist in self.metric_categories.items():
            for m in mlist:
                metric_to_cat[m] = cat
        long["category"] = long["metric"].map(metric_to_cat).fillna("Other")

        # Keep only numeric scores
        long = long[pd.to_numeric(long["score"], errors="coerce").notna()].copy()
        long["score"] = long["score"].astype(float)
        self.data_long = long

        if self.verbose:
            n_models = len(self.model_names)
            n_rows = len(self.data_long)
            n_metrics = self.data_long["metric"].nunique()
            print(f"Loaded {n_models} models, {n_rows} rows, {n_metrics} metrics.")

    def _split_selector(self, analyze_split: str) -> pd.DataFrame:
        """
        analyze_split: 'forget', 'retain', or 'both'
        For 'both', we keep all and add a label; for 'forget'/'retain', we filter.
        """
        if analyze_split not in {"forget", "retain", "both"}:
            raise ValueError("analyze_split must be one of {'forget','retain','both'}")

        df = self.data_long.copy()
        if analyze_split == "forget":
            return df[df["is_forget"] == True].copy()
        elif analyze_split == "retain":
            return df[df["is_forget"] == False].copy()
        else:
            # both: add a label column for clarity in plots/tables
            df["split"] = np.where(df["is_forget"], "Forget", "Retain")
            return df

    @staticmethod
    def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
        a = np.asarray(a); b = np.asarray(b)
        na, nb = len(a), len(b)
        sa, sb = np.nanstd(a, ddof=1), np.nanstd(b, ddof=1)
        if na < 2 or nb < 2:
            return np.nan
        s_pooled = np.sqrt(((na - 1) * sa ** 2 + (nb - 1) * sb ** 2) / (na + nb - 2)) if (na + nb - 2) > 0 else np.nan
        if s_pooled is None or s_pooled == 0 or np.isnan(s_pooled):
            return np.nan
        return (np.nanmean(a) - np.nanmean(b)) / s_pooled

    def _pairwise_tests(
        self,
        arrays: Dict[str, np.ndarray],
        nonparametric: bool = True,
        alternative: str = "two-sided",
    ) -> pd.DataFrame:
        """
        Pairwise tests between models for a single metric (optionally per split).
        Default: Mann-Whitney U (non-parametric). Alternative: Welch t-test.
        Multiple testing correction applied across all pairs.
        """
        models = list(arrays.keys())
        pairs = []
        raw_p = []
        stats = []
        eff_d = []

        for i in range(len(models)):
            for j in range(i + 1, len(models)):
                m1, m2 = models[i], models[j]
                x, y = arrays[m1], arrays[m2]
                x = x[~np.isnan(x)]
                y = y[~np.isnan(y)]
                if len(x) == 0 or len(y) == 0:
                    stat, p = np.nan, np.nan
                    d = np.nan
                else:
                    if nonparametric:
                        stat, p = mannwhitneyu(x, y, alternative=alternative)
                    else:
                        stat, p = ttest_ind(x, y, equal_var=False)
                    d = self._cohens_d(x, y)
                pairs.append((m1, m2))
                raw_p.append(p)
                stats.append(stat)
                eff_d.append(d)

        # Multiple testing correction
        if len(raw_p) > 0 and np.isfinite(raw_p).any():
            _, p_adj, _, _ = multipletests(raw_p, alpha=self.alpha, method=self.correction)
        else:
            p_adj = [np.nan] * len(raw_p)

        rows = []
        for (m1, m2), stat, p, padj, d in zip(pairs, stats, raw_p, p_adj, eff_d):
            rows.append(
                {
                    "Model1": m1,
                    "Model2": m2,
                    "TestStat": stat,
                    "p_raw": p,
                    "p_adj": padj,
                    "Significant": "Yes" if (padj < self.alpha) else "No",
                    "Cohen_d": d,
                }
            )
        return pd.DataFrame(rows)

    def compute_per_metric_statistics(self, analyze_split: str = "both") -> pd.DataFrame:
        """
        For each metric (and optionally each split), compute:
        - per-model N, mean, std
        - omnibus test (Kruskal–Wallis by default)
        - pairwise tests with Holm correction
        - model ranks by mean (lower-is-better or higher-is-better option could be added; here higher=better),
          with average ranks for ties
        """
        df = self._split_selector(analyze_split)
        results = []
        posthoc_records = []

        # Whether higher is better: here assumed higher=better for all metrics in your schema
        # If needed, introduce a per-metric direction map.
        higher_is_better = {m: True for m in df["metric"].unique()}

        group_cols = ["metric", "metric_clean", "category"]
        if analyze_split == "both":
            group_cols.append("split")

        for keys, g in df.groupby(group_cols, dropna=False):
            # keys is tuple of the grouping values
            key_dict = dict(zip(group_cols, keys if isinstance(keys, tuple) else [keys]))

            # Compute per-model descriptive stats
            desc = (
                g.groupby("model")["score"]
                .agg(N="count", Mean="mean", Std="std", Median="median")
                .reset_index()
            )

            # Ranks (higher mean = better)
            direction = higher_is_better[key_dict["metric"]]
            # Rank models by mean (average ranks for ties)
            desc["Rank"] = desc["Mean"].rank(
                ascending=not direction, method="average"
            )

            # Omnibus test across models (Kruskal by default)
            arrays = {m: x.values for m, x in g.groupby("model")["score"]}
            valid_arrays = [v[~np.isnan(v)] for v in arrays.values() if len(v) > 0]
            if len(valid_arrays) >= 2 and all(len(v) > 0 for v in valid_arrays):
                if self.prefer_nonparametric:
                    try:
                        H, p_omni = kruskal(*valid_arrays)
                        omni_name = "Kruskal"
                        omni_stat = H
                    except Exception:
                        omni_name = "Kruskal"
                        omni_stat, p_omni = np.nan, np.nan
                else:
                    # If you want Welch-ANOVA (needs statsmodels), you can extend here.
                    omni_name = "Kruskal"
                    try:
                        H, p_omni = kruskal(*valid_arrays)
                        omni_stat = H
                    except Exception:
                        omni_stat, p_omni = np.nan, np.nan
            else:
                omni_name, omni_stat, p_omni = "Kruskal", np.nan, np.nan

            # Pairwise post-hoc tests with multiple-testing correction
            ph = self._pairwise_tests(
                arrays=arrays, nonparametric=self.prefer_nonparametric
            )
            # Attach identifiers
            for _, row in ph.iterrows():
                posthoc_records.append(
                    {
                        **key_dict,
                        "Model1": row["Model1"],
                        "Model2": row["Model2"],
                        "Test": "MWU" if self.prefer_nonparametric else "WelchT",
                        "TestStat": row["TestStat"],
                        "p_raw": row["p_raw"],
                        "p_adj": row["p_adj"],
                        "Significant": row["Significant"],
                        "Cohen_d": row["Cohen_d"],
                    }
                )

            # Collect per-model stats rows
            for _, r in desc.iterrows():
                results.append(
                    {
                        **key_dict,
                        "Model": r["model"],
                        "N": int(r["N"]),
                        "Mean": r["Mean"],
                        "Std": r["Std"],
                        "Median": r["Median"],
                        "Rank": r["Rank"],
                        "Omnibus_Test": omni_name,
                        "Omnibus_Stat": omni_stat,
                        "Omnibus_p": p_omni,
                    }
                )

        self.per_metric_stats = pd.DataFrame(results)
        self.posthoc_df = pd.DataFrame(posthoc_records)
        return self.per_metric_stats

    def compute_category_aggregates(self, analyze_split: str = "both") -> pd.DataFrame:
        """
        Aggregates by category per model. Uses simple mean across metrics within category per sample,
        then aggregates by model. This preserves per-sample variability before model-level summary.
        """
        df = self._split_selector(analyze_split).copy()
        # Per-sample per-category average
        # We need to average across metrics for the same (model, sample, category)
        sample_key = ["model", "ti_id"]
        if analyze_split == "both":
            sample_key.append("split")
        agg = (
            df.groupby(sample_key + ["category"])["score"]
            .mean()
            .reset_index(name="score_cat")
        )
        # Now summarize per model/category
        cat_stats = (
            agg.groupby(["model", "category"] + (["split"] if analyze_split == "both" else []))["score_cat"]
            .agg(N="count", Mean="mean", Std="std", Median="median")
            .reset_index()
        )
        self.per_category_stats = cat_stats
        return self.per_category_stats

    def compute_overall_ranks(self, analyze_split: str = "both") -> pd.DataFrame:
        """
        Computes overall ranks per model by averaging metric ranks (higher-is-better).
        Outputs average rank and wins per metric (count of best ranks).
        """
        if self.per_metric_stats is None:
            raise RuntimeError("Call compute_per_metric_statistics first.")

        cols = ["metric", "metric_clean", "category", "Model", "Rank"]
        if analyze_split == "both":
            cols.insert(0, "split")

        df = self.per_metric_stats[cols].copy()

        # Average rank per model (and split if present)
        group_cols = ["Model"]
        if analyze_split == "both":
            group_cols.insert(0, "split")

        avg_rank = df.groupby(group_cols)["Rank"].mean().reset_index(name="AvgRank")

        # Count wins (Rank minimal)
        def count_wins(sub):
            min_rank = sub["Rank"].min()
            winners = (sub["Rank"] == min_rank).sum()
            return winners

        wins = (
            df.groupby(group_cols + ["metric_clean"])
            .apply(lambda s: s["Rank"] == s["Rank"].min())
            .reset_index(name="is_win")
        )
        wins = (
            wins.groupby(group_cols)["is_win"]
            .sum()
            .reset_index(name="MetricWins")
        )

        ranks = pd.merge(avg_rank, wins, on=group_cols, how="left")
        self.ranks_df = ranks
        return self.ranks_df

    # ===================
    # Visualization
    # ===================

    def plot_metric_violins(
        self,
        out_dir: Union[str, Path],
        analyze_split: str = "both",
        figsize: Tuple[int, int] = (18, 10),
    ):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        df = self._split_selector(analyze_split)

        metrics = df["metric"].unique()
        n = len(metrics)
        n_cols = 3
        n_rows = int(np.ceil(n / n_cols))

        fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
        axes = axes.flatten()

        for i, metric in enumerate(metrics):
            ax = axes[i]
            sub = df[df["metric"] == metric].copy()
            if analyze_split == "both":
                sns.violinplot(
                    data=sub, x="model", y="score", hue="split",
                    inner="quartile", cut=0, ax=ax
                )
                ax.legend_.remove()
            else:
                sns.violinplot(
                    data=sub, x="model", y="score", inner="quartile", cut=0, ax=ax
                )
            ax.set_title(sub["metric_clean"].iloc[0], fontsize=10, fontweight="bold")
            ax.set_xlabel("")
            ax.set_ylabel("Score")
            ax.grid(True, axis="y", alpha=0.3)
            ax.tick_params(axis="x", rotation=30)

        for j in range(i + 1, len(axes)):
            axes[j].axis("off")

        plt.tight_layout()
        fpath = out_dir / ("metric_violins.png" if analyze_split != "both" else "metric_violins_split.png")
        plt.savefig(fpath, dpi=300, bbox_inches="tight")
        plt.close()
        if self.verbose:
            print(f"✓ Saved {fpath}")

    def plot_metric_boxplots(
        self,
        out_dir: Union[str, Path],
        analyze_split: str = "both",
        figsize: Tuple[int, int] = (18, 10),
    ):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        df = self._split_selector(analyze_split)

        metrics = df["metric"].unique()
        n = len(metrics)
        n_cols = 3
        n_rows = int(np.ceil(n / n_cols))

        fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
        axes = axes.flatten()

        for i, metric in enumerate(metrics):
            ax = axes[i]
            sub = df[df["metric"] == metric].copy()
            if analyze_split == "both":
                sns.boxplot(
                    data=sub, x="model", y="score", hue="split",
                    showfliers=False, ax=ax
                )
                ax.legend_.remove()
            else:
                sns.boxplot(
                    data=sub, x="model", y="score", showfliers=False, ax=ax
                )
            # overlay means
            means = sub.groupby(["model"] + (["split"] if analyze_split == "both" else []))["score"].mean().reset_index()
            if analyze_split == "both":
                for split in ["Forget", "Retain"]:
                    ms = means[means.get("split", split) == split]
                    ax.scatter(
                        x=np.arange(len(ms["model"].unique())),
                        y=ms["score"],
                        marker="D", color="red", zorder=3, s=35, label=None
                    )
            else:
                ms = means
                ax.scatter(
                    x=np.arange(len(ms["model"].unique())),
                    y=ms["score"],
                    marker="D", color="red", zorder=3, s=35, label=None
                )

            ax.set_title(sub["metric_clean"].iloc[0], fontsize=10, fontweight="bold")
            ax.set_xlabel("")
            ax.set_ylabel("Score")
            ax.grid(True, axis="y", alpha=0.3)
            ax.tick_params(axis="x", rotation=30)

        for j in range(i + 1, len(axes)):
            axes[j].axis("off")

        plt.tight_layout()
        fpath = out_dir / ("metric_boxplots.png" if analyze_split != "both" else "metric_boxplots_split.png")
        plt.savefig(fpath, dpi=300, bbox_inches="tight")
        plt.close()
        if self.verbose:
            print(f"✓ Saved {fpath}")

    def plot_mean_heatmap(
        self, out_dir: Union[str, Path], analyze_split: str = "both", figsize=(14, 8)
    ):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        df = self._split_selector(analyze_split)

        if analyze_split == "both":
            pivot = (
                df.groupby(["metric_clean", "model", "split"])["score"]
                .mean()
                .reset_index()
                .pivot_table(
                    index=["model"],
                    columns=["metric_clean", "split"],
                    values="score",
                )
            )
        else:
            pivot = (
                df.groupby(["metric_clean", "model"])["score"]
                .mean()
                .reset_index()
                .pivot(index="model", columns="metric_clean", values="score")
            )

        plt.figure(figsize=figsize)
        sns.heatmap(pivot, annot=True, fmt=".3f", cmap="RdYlGn", vmin=0, vmax=1,
                    cbar_kws={"label": "Mean Score"}, linewidths=0.5)
        plt.title("Mean Scores by Model" + ("" if analyze_split != "both" else " (Forget/Retain)"))
        plt.xlabel("")
        plt.ylabel("")
        plt.tight_layout()
        fpath = out_dir / ("mean_heatmap.png" if analyze_split != "both" else "mean_heatmap_split.png")
        plt.savefig(fpath, dpi=300, bbox_inches="tight")
        plt.close()
        if self.verbose:
            print(f"✓ Saved {fpath}")

    def plot_rank_bar(
        self, out_dir: Union[str, Path], analyze_split: str = "both", figsize=(10, 6)
    ):
        if self.ranks_df is None:
            raise RuntimeError("Call compute_overall_ranks first.")
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        df = self.ranks_df.copy()
        plt.figure(figsize=figsize)
        if analyze_split == "both":
            sns.barplot(data=df, x="Model", y="AvgRank", hue="split")
        else:
            sns.barplot(data=df, x="Model", y="AvgRank")
        plt.gca().invert_yaxis()  # better rank = smaller number
        plt.title("Average Rank (lower is better)")
        plt.ylabel("Average Rank")
        plt.xlabel("")
        plt.grid(True, axis="y", alpha=0.3)
        plt.tight_layout()
        fpath = out_dir / ("avg_rank.png" if analyze_split != "both" else "avg_rank_split.png")
        plt.savefig(fpath, dpi=300, bbox_inches="tight")
        plt.close()
        if self.verbose:
            print(f"✓ Saved {fpath}")

    # ===================
    # Exporters
    # ===================

    def export_results(self, out_dir: Union[str, Path]):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        # CSVs
        if self.per_metric_stats is not None:
            self.per_metric_stats.to_csv(out_dir / "per_metric_stats.csv", index=False)
        if self.per_category_stats is not None:
            self.per_category_stats.to_csv(out_dir / "per_category_stats.csv", index=False)
        if self.posthoc_df is not None:
            self.posthoc_df.to_csv(out_dir / "posthoc_tests.csv", index=False)
        if self.ranks_df is not None:
            self.ranks_df.to_csv(out_dir / "overall_ranks.csv", index=False)

        # Excel workbook
        try:
            with pd.ExcelWriter(out_dir / "multimodel_comparison.xlsx", engine="openpyxl") as writer:
                if self.per_metric_stats is not None:
                    self.per_metric_stats.to_excel(writer, sheet_name="PerMetric", index=False)
                if self.per_category_stats is not None:
                    self.per_category_stats.to_excel(writer, sheet_name="PerCategory", index=False)
                if self.posthoc_df is not None:
                    self.posthoc_df.to_excel(writer, sheet_name="PostHoc", index=False)
                if self.ranks_df is not None:
                    self.ranks_df.to_excel(writer, sheet_name="Ranks", index=False)
        except Exception as e:
            if self.verbose:
                print(f"[WARN] Excel export failed: {e}. CSVs were saved.")

        if self.verbose:
            print("✓ Saved tables (CSV/Excel)")

    def generate_text_summary(self, analyze_split: str = "both") -> str:
        """
        Concise textual overview for a paper appendix or methods/results section.
        """
        if self.per_metric_stats is None or self.ranks_df is None:
            raise RuntimeError("Run statistics and ranks before generating summary.")

        lines = []
        lines.append("=" * 80)
        lines.append("MULTI-MODEL UNLEARNING COMPARISON SUMMARY")
        lines.append("=" * 80)
        lines.append("")
        # Overall ranking
        lines.append("OVERALL MODEL RANKING (lower AvgRank is better):")
        if analyze_split == "both":
            for split, sub in self.ranks_df.groupby("split"):
                sub = sub.sort_values("AvgRank")
                lines.append(f"  Split: {split}")
                for _, r in sub.iterrows():
                    lines.append(f"    {r['Model']}: AvgRank={r['AvgRank']:.2f}, MetricWins={int(r['MetricWins'])}")
        else:
            sub = self.ranks_df.sort_values("AvgRank")
            for _, r in sub.iterrows():
                lines.append(f"  {r['Model']}: AvgRank={r['AvgRank']:.2f}, MetricWins={int(r['MetricWins'])}")
        lines.append("")

        # Per metric highlights: winners + omnibus significance
        df = self.per_metric_stats.copy()
        if analyze_split == "both":
            group_cols = ["metric_clean", "split"]
        else:
            group_cols = ["metric_clean"]

        lines.append("PER-METRIC HIGHLIGHTS:")
        for keys, g in df.groupby(group_cols):
            if isinstance(keys, tuple):
                metric, split = keys
                header = f"  {metric} [{split}]"
            else:
                metric = keys
                header = f"  {metric}"
            lines.append(header)
            # winner(s) by rank
            min_rank = g["Rank"].min()
            winners = g[g["Rank"] == min_rank]["Model"].tolist()
            lines.append(f"    Best: {', '.join(winners)} (Rank={min_rank:.1f})")
            # omnibus
            p = g["Omnibus_p"].iloc[0]
            lines.append(f"    Omnibus (Kruskal) p={p:.4g}" if pd.notna(p) else "    Omnibus: n/a")
        lines.append("")
        lines.append("=" * 80)
        return "\n".join(lines)

    def run_full_comparison(
        self,
        out_dir: Union[str, Path] = "mmu_outputs",
        analyze_split: str = "both",
    ):
        """
        Full pipeline:
        - per metric statistics
        - per category aggregates
        - overall ranks
        - plots
        - export tables
        - print summary
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        if self.verbose:
            print("\n" + "=" * 80)
            print("STARTING MULTI-MODEL UNLEARNING COMPARISON")
            print("=" * 80 + "\n")

        # Stats
        if self.verbose:
            print("1) Computing per-metric statistics...")
        self.compute_per_metric_statistics(analyze_split=analyze_split)
        if self.verbose:
            print("   ✓ Done.")

        if self.verbose:
            print("2) Computing per-category aggregates...")
        self.compute_category_aggregates(analyze_split=analyze_split)
        if self.verbose:
            print("   ✓ Done.")

        if self.verbose:
            print("3) Computing overall ranks...")
        self.compute_overall_ranks(analyze_split=analyze_split)
        if self.verbose:
            print("   ✓ Done.")

        if self.verbose:
            print("4) Generating plots...")
        self.plot_metric_violins(out_dir=out_dir, analyze_split=analyze_split)
        self.plot_metric_boxplots(out_dir=out_dir, analyze_split=analyze_split)
        self.plot_mean_heatmap(out_dir=out_dir, analyze_split=analyze_split)
        self.plot_rank_bar(out_dir=out_dir, analyze_split=analyze_split)
        if self.verbose:
            print("   ✓ Plots saved.")

        if self.verbose:
            print("5) Exporting tables...")
        self.export_results(out_dir=out_dir)
        if self.verbose:
            print("   ✓ Tables saved.")

        if self.verbose:
            print("6) Summary:")
        summary = self.generate_text_summary(analyze_split=analyze_split)
        print(summary)

        if self.verbose:
            print("\nArtifacts written to:", out_dir)
            print("Figures:")
            print("  metric_violins*.png")
            print("  metric_boxplots*.png")
            print("  mean_heatmap*.png")
            print("  avg_rank*.png")
            print("Tables:")
            print("  per_metric_stats.csv")
            print("  per_category_stats.csv")
            print("  posthoc_tests.csv")
            print("  overall_ranks.csv")
            print("  multimodel_comparison.xlsx")