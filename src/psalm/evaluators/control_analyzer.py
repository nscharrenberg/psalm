from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import warnings

warnings.filterwarnings("ignore")

plt.style.use("seaborn-v0_8-darkgrid")
sns.set_palette("husl")


class ControlValidationAnalyzer:
    """Analyzes control experiments validating PSALM evaluator behavior."""

    def __init__(self, results_dir: Path, output_dir: Path):
        self.results_dir = Path(results_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Define evaluator categories
        self.evaluator_categories = {
            "Stylistic": ["Writing Style", "Narrative Voice"],
            "Content": [
                "Character Similarity",
                "Plot Structure Similarity",
                "Scene Sequence Similarity",
                "World Building Similarity",
            ],
            "Exceptions": [
                "Parody Satire",
                "Pastiche",
                "Quotation Citation",
                "Scènes à Faire",
            ],
        }

        self.all_evaluators = []
        for evals in self.evaluator_categories.values():
            self.all_evaluators.extend(evals)

        self.results_df: Optional[pd.DataFrame] = None
        self.validation_summary: Optional[pd.DataFrame] = None

    # -------------------------------------------------------------------------
    # Loading + metrics (unchanged from your logic, just copied)
    # -------------------------------------------------------------------------

    def _clean_evaluator_name(self, filename: str) -> str:
        name = filename.replace(".json", "")
        parts = [p.capitalize() for p in name.split("_")]
        name_joined = " ".join(parts)

        replacements = {
            "A Faire": "à Faire",
            "Parody Satire": "Parody Satire",
            "Quotation Citation": "Quotation Citation",
        }
        for old, new in replacements.items():
            name_joined = name_joined.replace(old, new)
        return name_joined

    def load_results(self) -> pd.DataFrame:
        records = []
        for eval_file in self.results_dir.glob("*.json"):
            evaluator_name = self._clean_evaluator_name(eval_file.name)
            print(f"  Loading {eval_file.name} -> {evaluator_name}")
            with open(eval_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for test_case_name, test_case_data in data.items():
                expected_score = test_case_data.get("expected_score", np.nan)
                runs = test_case_data.get("runs", [])

                for run_idx, run_data in enumerate(runs):
                    records.append(
                        {
                            "Evaluator": evaluator_name,
                            "Test_Case": test_case_name,
                            "Run_ID": run_idx + 1,
                            "Expected_Score": expected_score,
                            "Actual_Score": run_data.get("score", np.nan),
                            "Reasoning": run_data.get("reason", ""),
                        }
                    )

        if not records:
            raise ValueError(f"No results loaded from {self.results_dir}")

        self.results_df = pd.DataFrame(records)

        def get_category(evaluator: str) -> str:
            for cat, evals in self.evaluator_categories.items():
                for ev in evals:
                    if ev.lower() in evaluator.lower() or evaluator.lower() in ev.lower():
                        return cat
            return "Other"

        self.results_df["Category"] = self.results_df["Evaluator"].apply(get_category)

        self.results_df["Absolute_Error"] = (
            self.results_df["Actual_Score"] - self.results_df["Expected_Score"]
        ).abs()
        self.results_df["Squared_Error"] = (
            self.results_df["Actual_Score"] - self.results_df["Expected_Score"]
        ) ** 2

        def classify_alignment(row):
            error = abs(row["Actual_Score"] - row["Expected_Score"])
            if error <= 0.1:
                return "EXACT"
            elif error <= 0.2:
                return "CLOSE"
            elif error <= 0.3:
                return "ACCEPTABLE"
            else:
                return "POOR"

        self.results_df["Alignment"] = self.results_df.apply(classify_alignment, axis=1)

        print(f"\n✓ Loaded {len(self.results_df)} test runs")
        print(f"  Evaluators: {self.results_df['Evaluator'].nunique()}")
        print(f"  Test Cases: {self.results_df['Test_Case'].nunique()}")
        print(f"  Total Runs: {len(self.results_df)}")
        return self.results_df

    def compute_validation_metrics(self) -> pd.DataFrame:
        results = []
        for evaluator in self.results_df["Evaluator"].unique():
            eval_data = self.results_df[self.results_df["Evaluator"] == evaluator].copy()

            mean_abs_error = eval_data["Absolute_Error"].mean()
            median_abs_error = eval_data["Absolute_Error"].median()
            max_abs_error = eval_data["Absolute_Error"].max()
            rmse = np.sqrt(eval_data["Squared_Error"].mean())

            exact = len(eval_data[eval_data["Alignment"] == "EXACT"])
            close = len(eval_data[eval_data["Alignment"] == "CLOSE"])
            acceptable = len(eval_data[eval_data["Alignment"] == "ACCEPTABLE"])
            poor = len(eval_data[eval_data["Alignment"] == "POOR"])
            total = len(eval_data)

            success_rate = (exact + close + acceptable) / total if total > 0 else 0
            strict_success_rate = (exact + close) / total if total > 0 else 0

            cv_error = (
                eval_data["Absolute_Error"].std() / mean_abs_error
                if mean_abs_error > 0
                else np.nan
            )

            if strict_success_rate >= 0.8 and mean_abs_error <= 0.15:
                validated = "Yes"
            elif success_rate >= 0.7 and mean_abs_error <= 0.25:
                validated = "Partial"
            else:
                validated = "No"

            results.append(
                {
                    "Evaluator": evaluator,
                    "Category": eval_data["Category"].iloc[0],
                    "N_Runs": total,
                    "N_Test_Cases": eval_data["Test_Case"].nunique(),
                    "Mean_Abs_Error": mean_abs_error,
                    "Median_Abs_Error": median_abs_error,
                    "Max_Abs_Error": max_abs_error,
                    "RMSE": rmse,
                    "Exact_Count": exact,
                    "Close_Count": close,
                    "Acceptable_Count": acceptable,
                    "Poor_Count": poor,
                    "Success_Rate": success_rate,
                    "Strict_Success_Rate": strict_success_rate,
                    "Error_CV": cv_error,
                    "Validated": validated,
                }
            )

        self.validation_summary = pd.DataFrame(results)
        return self.validation_summary

    # -------------------------------------------------------------------------
    # VISUALS
    # -------------------------------------------------------------------------

    def plot_score_heatmap(self, figsize=(18, 10)):
        """Side-by-side heatmaps of expected and mean actual scores per test case."""
        agg_data = (
            self.results_df.groupby(["Evaluator", "Test_Case"])
            .agg({"Expected_Score": "first", "Actual_Score": "mean"})
            .reset_index()
        )

        pivot_expected = agg_data.pivot_table(
            index="Evaluator",
            columns="Test_Case",
            values="Expected_Score",
            aggfunc="first",
        )
        pivot_actual = agg_data.pivot_table(
            index="Evaluator",
            columns="Test_Case",
            values="Actual_Score",
            aggfunc="mean",
        )

        evaluators = sorted(pivot_expected.index)
        pivot_expected = pivot_expected.loc[evaluators]
        pivot_actual = pivot_actual.loc[evaluators]

        fig, axes = plt.subplots(1, 2, figsize=figsize)

        sns.heatmap(
            pivot_expected,
            annot=True,
            fmt=".1f",
            cmap="RdYlGn",
            center=0.5,
            vmin=0,
            vmax=1,
            cbar_kws={"label": "Score"},
            linewidths=0.5,
            ax=axes[0],
        )
        axes[0].set_title(
            "Expected Scores per Evaluator/Test Case", fontsize=14, fontweight="bold"
        )
        axes[0].set_xlabel("")
        axes[0].set_ylabel("Evaluator", fontsize=11)

        sns.heatmap(
            pivot_actual,
            annot=True,
            fmt=".1f",
            cmap="RdYlGn",
            center=0.5,
            vmin=0,
            vmax=1,
            cbar_kws={"label": "Score"},
            linewidths=0.5,
            ax=axes[1],
        )
        axes[1].set_title(
            "Mean Actual Scores per Evaluator/Test Case",
            fontsize=14,
            fontweight="bold",
        )
        axes[1].set_xlabel("")
        axes[1].set_ylabel("")

        plt.suptitle(
            "PSALM Evaluator Performance: Expected vs Actual",
            fontsize=16,
            fontweight="bold",
            y=0.98,
        )
        plt.tight_layout()
        fpath = self.output_dir / "validation_heatmap.png"
        plt.savefig(fpath, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"✓ Saved {fpath}")
        return fig

    # 1. Absolute Error by Evaluator (separate figure, clearer)
    def plot_absolute_error_by_evaluator(self, figsize=(10, 6)):
        """Boxplot of absolute error distributions per evaluator."""
        eval_order = (
            self.results_df.groupby("Evaluator")["Absolute_Error"].mean().sort_values().index
        )
        fig, ax = plt.subplots(figsize=figsize)
        sns.boxplot(
            data=self.results_df,
            y="Evaluator",
            x="Absolute_Error",
            order=eval_order,
            ax=ax,
        )
        ax.axvline(0.1, color="green", linestyle="--", label="Exact threshold (≤0.1)")
        ax.axvline(0.2, color="orange", linestyle="--", label="Close threshold (≤0.2)")
        ax.set_title(
            "Absolute Error Distribution per Evaluator", fontsize=13, fontweight="bold"
        )
        ax.set_xlabel("Absolute Error |Actual − Expected|", fontsize=11)
        ax.set_ylabel("Evaluator", fontsize=11)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis="x")
        fpath = self.output_dir / "absolute_error_by_evaluator.png"
        plt.tight_layout()
        plt.savefig(fpath, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"✓ Saved {fpath}")
        return fig

    # 2. Expected vs Actual scatter with category-based colors and proper legend
    def plot_expected_vs_actual_scatter(self, figsize=(8, 7)):
        """
        Scatter of expected vs mean actual scores, colored by evaluator category.

        Each point = one evaluator–test-case pair.
        Color = category (colorblind-friendly).
        Jitter is added to reduce overplotting of identical scores.
        """
        if self.results_df is None:
            raise RuntimeError("Run load_results() first")

        agg = (
            self.results_df.groupby(["Evaluator", "Test_Case", "Category"])
            .agg({"Expected_Score": "first", "Actual_Score": "mean"})
            .reset_index()
        )

        # Colorblind-friendly palette (Okabe–Ito style)
        category_colors = {
            "Stylistic": "#0072B2",  # blue
            "Content": "#009E73",  # green
            "Exceptions": "#D55E00",  # vermilion
            "Other": "#999999",  # grey
        }

        fig, ax = plt.subplots(figsize=figsize)

        # ------------------------------------------------------------------
        # 1. Reference line + bands FIRST (so points are on top)
        # ------------------------------------------------------------------
        x_line = np.linspace(0, 1, 200)
        perfect = x_line

        # ±0.1 band
        lower_01 = np.clip(perfect - 0.1, 0, 1)
        upper_01 = np.clip(perfect + 0.1, 0, 1)
        ax.fill_between(
            x_line,
            lower_01,
            upper_01,
            alpha=0.15,
            color="grey",
            label="±0.1 band",
        )

        # ±0.2 band
        lower_02 = np.clip(perfect - 0.2, 0, 1)
        upper_02 = np.clip(perfect + 0.2, 0, 1)
        ax.fill_between(
            x_line,
            lower_02,
            upper_02,
            alpha=0.08,
            color="lightgrey",
            label="±0.2 band",
        )

        ax.plot(
            [0, 1],
            [0, 1],
            "k--",
            linewidth=2,
            label="Perfect agreement",
            zorder=1,
        )

        # ------------------------------------------------------------------
        # 2. Points, with small jitter to reduce overlap
        # ------------------------------------------------------------------
        rng = np.random.default_rng(42)  # deterministic jitter for reproducibility
        jitter_scale = 0.012  # within a ±0.012 box in both directions

        for cat, cat_df in agg.groupby("Category"):
            # Add symmetric jitter in both directions
            jitter_x = rng.uniform(-jitter_scale, jitter_scale, size=len(cat_df))
            jitter_y = rng.uniform(-jitter_scale, jitter_scale, size=len(cat_df))

            x_vals = np.clip(cat_df["Expected_Score"].values + jitter_x, 0, 1)
            y_vals = np.clip(cat_df["Actual_Score"].values + jitter_y, 0, 1)

            ax.scatter(
                x_vals,
                y_vals,
                label=cat,
                alpha=0.9,
                s=50,
                color=category_colors.get(cat, "#999999"),
                edgecolors="black",
                linewidth=0.6,
                zorder=2,
            )

        ax.set_xlabel("Expected Score", fontsize=11)
        ax.set_ylabel("Mean Actual Score", fontsize=11)
        ax.set_title(
            "Expected vs Mean Actual Scores\n(Colored by Evaluator Category)",
            fontsize=13,
            fontweight="bold",
        )
        ax.set_xlim(-0.05, 1.05)
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, alpha=0.3)

        # Combine legend entries: first bands/line, then categories
        handles, labels = ax.get_legend_handles_labels()
        # Ensure unique labels in order of first appearance
        seen = set()
        uniq_handles, uniq_labels = [], []
        for h, l in zip(handles, labels):
            if l not in seen:
                seen.add(l)
                uniq_handles.append(h)
                uniq_labels.append(l)

        ax.legend(
            uniq_handles,
            uniq_labels,
            title="Reference / Category",
            fontsize=9,
            loc="upper left",
        )

        fpath = self.output_dir / "expected_vs_actual_scatter.png"
        plt.tight_layout()
        plt.savefig(fpath, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"✓ Saved {fpath}")
        return fig

    # 3. Alignment distribution stacked bar (separate figure)
    def plot_alignment_distribution(self, figsize=(10, 6)):
        """Stacked bar chart of EXTACT/CLOSE/ACCEPTABLE/POOR counts per evaluator."""
        alignment_counts = (
            self.results_df.groupby(["Evaluator", "Alignment"]).size().unstack(fill_value=0)
        )
        eval_order = (
            self.results_df.groupby("Evaluator")["Absolute_Error"].mean().sort_values().index
        )
        alignment_counts = alignment_counts.loc[eval_order]

        fig, ax = plt.subplots(figsize=figsize)
        alignment_counts.plot(
            kind="barh",
            stacked=True,
            ax=ax,
            color={"EXACT": "#2ecc71", "CLOSE": "#3498db", "ACCEPTABLE": "#f39c12", "POOR": "#e74c3c"},
        )
        ax.set_title(
            "Alignment Classification per Evaluator", fontsize=13, fontweight="bold"
        )
        ax.set_xlabel("Number of Runs", fontsize=11)
        ax.set_ylabel("Evaluator", fontsize=11)
        ax.legend(title="Alignment", fontsize=9)
        ax.grid(True, alpha=0.3, axis="x")
        fpath = self.output_dir / "alignment_distribution.png"
        plt.tight_layout()
        plt.savefig(fpath, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"✓ Saved {fpath}")
        return fig

    # 4. Error distribution by category with legend explaining markers/lines
    def plot_error_distribution_by_category(self, figsize=(7, 6)):
        """
        Boxplot of absolute error per category.

        - Boxes = IQR per category
        - Mean shown as a diamond marker
        - Horizontal dashed lines = exact/close thresholds (0.1, 0.2)
        """
        categories = ["Stylistic", "Content", "Exceptions"]
        data = []
        labels = []
        for cat in categories:
            cat_errors = self.results_df[self.results_df["Category"] == cat][
                "Absolute_Error"
            ].dropna()
            if len(cat_errors) > 0:
                data.append(cat_errors.values)
                labels.append(cat)

        fig, ax = plt.subplots(figsize=figsize)
        bp = ax.boxplot(
            data,
            labels=labels,
            patch_artist=True,
            showmeans=False,
        )

        colors = ["#e74c3c", "#3498db", "#2ecc71"]
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.55)

        # Add mean markers manually (diamond)
        for i, cat_data in enumerate(data, start=1):
            mean_val = np.mean(cat_data)
            ax.scatter(
                i,
                mean_val,
                marker="D",
                s=60,
                color="black",
                label="Mean" if i == 1 else None,
                zorder=3,
            )

        # Threshold lines with labels in legend
        ax.axhline(
            0.1, color="green", linestyle="--", linewidth=1.5, alpha=0.7, label="Exact (0.1)"
        )
        ax.axhline(
            0.2, color="orange", linestyle="--", linewidth=1.5, alpha=0.7, label="Close (0.2)"
        )

        ax.set_title(
            "Absolute Error Distribution by Category", fontsize=13, fontweight="bold"
        )
        ax.set_ylabel("Absolute Error |Actual − Expected|", fontsize=11)
        ax.set_xlabel("Evaluator Category", fontsize=11)
        ax.grid(True, alpha=0.3, axis="y")
        ax.legend(fontsize=9)
        fpath = self.output_dir / "error_distribution_by_category.png"
        plt.tight_layout()
        plt.savefig(fpath, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"✓ Saved {fpath}")
        return fig

    # 5. Validation summary (rename right-hand title to explicitly say what it shows)
    def plot_validation_summary(self, figsize=(14, 8)):
        """Summary of success rates and mean absolute error per evaluator."""
        if self.validation_summary is None:
            raise RuntimeError("Run compute_validation_metrics() first")

        df = self.validation_summary.sort_values("Strict_Success_Rate", ascending=True)
        fig, axes = plt.subplots(1, 2, figsize=figsize)

        # Left: Success rates
        ax1 = axes[0]
        x = np.arange(len(df))
        width = 0.35

        colors_strict = df["Validated"].map(
            {"Yes": "#2ecc71", "Partial": "#f39c12", "No": "#e74c3c"}
        )

        ax1.barh(
            x - width / 2,
            df["Strict_Success_Rate"],
            width,
            label="Strict (EXACT+CLOSE)",
            color=colors_strict,
            alpha=0.8,
            edgecolor="black",
            linewidth=1,
        )
        ax1.barh(
            x + width / 2,
            df["Success_Rate"],
            width,
            label="Lenient (EXACT+CLOSE+ACCEPTABLE)",
            color="#95a5a6",
            alpha=0.6,
            edgecolor="black",
            linewidth=1,
        )

        ax1.axvline(
            0.8,
            color="green",
            linestyle="--",
            linewidth=2,
            alpha=0.7,
            label="Validation threshold (0.8)",
        )
        ax1.axvline(
            0.7,
            color="orange",
            linestyle="--",
            linewidth=2,
            alpha=0.7,
            label="Partial threshold (0.7)",
        )

        ax1.set_yticks(x)
        ax1.set_yticklabels(df["Evaluator"], fontsize=9)
        ax1.set_xlabel("Success Rate", fontsize=11, fontweight="bold")
        ax1.set_title("Success Rates per Evaluator", fontsize=12, fontweight="bold")
        ax1.set_xlim(0, 1.05)
        ax1.legend(loc="lower right", fontsize=8)
        ax1.grid(True, alpha=0.3, axis="x")

        # Right: Mean absolute error
        ax2 = axes[1]
        df_sorted = df.sort_values("Mean_Abs_Error", ascending=True)

        ax2.barh(
            df_sorted["Evaluator"],
            df_sorted["Mean_Abs_Error"],
            color=df_sorted["Validated"].map(
                {"Yes": "#2ecc71", "Partial": "#f39c12", "No": "#e74c3c"}
            ),
            alpha=0.7,
            edgecolor="black",
            linewidth=1,
        )

        ax2.errorbar(
            df_sorted["Mean_Abs_Error"],
            np.arange(len(df_sorted)),
            xerr=df_sorted["RMSE"] - df_sorted["Mean_Abs_Error"],
            fmt="none",
            ecolor="black",
            alpha=0.5,
            capsize=3,
        )

        ax2.axvline(
            0.15,
            color="green",
            linestyle="--",
            linewidth=2,
            alpha=0.7,
            label="Validation threshold (0.15)",
        )
        ax2.axvline(
            0.25,
            color="orange",
            linestyle="--",
            linewidth=2,
            alpha=0.7,
            label="Partial threshold (0.25)",
        )

        ax2.set_xlabel("Mean Absolute Error", fontsize=11, fontweight="bold")
        ax2.set_title(
            "Mean Absolute Error per Evaluator",  # renamed (was 'Prediction Accuracy')
            fontsize=12,
            fontweight="bold",
        )
        ax2.set_xlim(0, max(df_sorted["Mean_Abs_Error"].max() * 1.1, 0.4))
        ax2.legend(loc="upper right", fontsize=8)
        ax2.grid(True, alpha=0.3, axis="x")

        plt.suptitle(
            "PSALM Evaluator Validation Summary",
            fontsize=16,
            fontweight="bold",
            y=0.98,
        )
        plt.tight_layout()
        fpath = self.output_dir / "validation_summary.png"
        plt.savefig(fpath, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"✓ Saved {fpath}")
        return fig

    # 6. Test-case detail unchanged (still a grid, but logically separate file)
    def plot_test_case_detail(self, figsize=(16, 12)):
        test_case_agg = (
            self.results_df.groupby(["Evaluator", "Test_Case"])
            .agg(
                {
                    "Expected_Score": "first",
                    "Actual_Score": ["mean", "std"],
                    "Absolute_Error": "mean",
                }
            )
            .reset_index()
        )
        test_case_agg.columns = [
            "Evaluator",
            "Test_Case",
            "Expected",
            "Actual_Mean",
            "Actual_Std",
            "Mean_Error",
        ]

        evaluators = sorted(test_case_agg["Evaluator"].unique())
        n_evals = len(evaluators)
        n_cols = 2
        n_rows = int(np.ceil(n_evals / n_cols))

        fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
        axes = np.atleast_1d(axes).flatten()

        for idx, evaluator in enumerate(evaluators):
            ax = axes[idx]
            eval_data = test_case_agg[test_case_agg["Evaluator"] == evaluator].copy()
            eval_data = eval_data.sort_values("Expected")
            x = np.arange(len(eval_data))

            ax.scatter(
                x,
                eval_data["Expected"],
                s=150,
                marker="s",
                color="#3498db",
                label="Expected",
                alpha=0.7,
                edgecolors="black",
                linewidth=1.5,
                zorder=3,
            )
            ax.errorbar(
                x,
                eval_data["Actual_Mean"],
                yerr=eval_data["Actual_Std"],
                fmt="o",
                markersize=9,
                color="#e74c3c",
                label="Actual (±SD)",
                alpha=0.7,
                capsize=5,
                capthick=2,
                elinewidth=2,
                markeredgecolor="black",
                markeredgewidth=1.5,
                zorder=3,
            )

            for i in range(len(eval_data)):
                ax.plot(
                    [i, i],
                    [eval_data["Expected"].iloc[i], eval_data["Actual_Mean"].iloc[i]],
                    "k--",
                    alpha=0.3,
                    linewidth=1,
                )

            ax.set_title(evaluator, fontsize=11, fontweight="bold")
            ax.set_xticks(x)
            ax.set_xticklabels([f"TC{i+1}" for i in range(len(eval_data))], fontsize=8)
            ax.set_ylabel("Score", fontsize=10)
            ax.set_ylim(-0.05, 1.05)
            ax.legend(loc="best", fontsize=8)
            ax.grid(True, alpha=0.3, axis="y")

        for idx in range(n_evals, len(axes)):
            axes[idx].axis("off")

        plt.suptitle(
            "Test Case Performance Detail (TC = Test Case)",
            fontsize=16,
            fontweight="bold",
            y=0.995,
        )
        plt.tight_layout()
        fpath = self.output_dir / "test_case_detail.png"
        plt.savefig(fpath, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"✓ Saved {fpath}")
        return fig

    # -------------------------------------------------------------------------
    # Export + summary + pipeline (unchanged except for mentioning new images)
    # -------------------------------------------------------------------------

    def export_results(self):
        self.results_df.to_csv(self.output_dir / "validation_results_raw.csv", index=False)

        if self.validation_summary is not None:
            self.validation_summary.to_csv(
                self.output_dir / "validation_summary.csv", index=False
            )

        test_case_summary = (
            self.results_df.groupby(["Evaluator", "Test_Case"])
            .agg(
                {
                    "Expected_Score": "first",
                    "Actual_Score": ["mean", "std", "min", "max"],
                    "Absolute_Error": ["mean", "std"],
                    "Alignment": lambda x: x.mode()[0] if len(x) > 0 else None,
                }
            )
            .reset_index()
        )
        test_case_summary.to_csv(
            self.output_dir / "test_case_summary.csv", index=False
        )

        try:
            with pd.ExcelWriter(
                self.output_dir / "validation_analysis.xlsx", engine="openpyxl"
            ) as writer:
                self.results_df.to_excel(writer, sheet_name="Raw Results", index=False)
                if self.validation_summary is not None:
                    self.validation_summary.to_excel(
                        writer, sheet_name="Validation Summary", index=False
                    )
                test_case_summary.to_excel(
                    writer, sheet_name="Test Case Summary", index=False
                )
        except Exception as e:
            print(f"[WARN] Excel export failed: {e}")

        print("✓ Exported validation results")

    def generate_text_summary(self) -> str:
        if self.validation_summary is None:
            raise RuntimeError("Run compute_validation_metrics() first")

        lines = []
        lines.append("=" * 80)
        lines.append("PSALM EVALUATOR VALIDATION SUMMARY (RQ1)")
        lines.append("=" * 80)
        lines.append("")

        total_evals = len(self.validation_summary)
        validated = len(self.validation_summary[self.validation_summary["Validated"] == "Yes"])
        partial = len(self.validation_summary[self.validation_summary["Validated"] == "Partial"])
        failed = len(self.validation_summary[self.validation_summary["Validated"] == "No"])

        lines.append("OVERALL VALIDATION STATUS:")
        lines.append(f"  Total Evaluators: {total_evals}")
        lines.append(f"  Fully Validated: {validated} ({validated/total_evals*100:.1f}%)")
        lines.append(f"  Partially Validated: {partial} ({partial/total_evals*100:.1f}%)")
        lines.append(f"  Failed Validation: {failed} ({failed/total_evals*100:.1f}%)")
        lines.append("")
        lines.append("VALIDATION BY CATEGORY:")
        for cat in ["Stylistic", "Content", "Exceptions"]:
            cat_summary = self.validation_summary[self.validation_summary["Category"] == cat]
            if len(cat_summary) == 0:
                continue
            lines.append(f"\n  {cat}:")
            for _, row in cat_summary.iterrows():
                status_symbol = (
                    "✓"
                    if row["Validated"] == "Yes"
                    else "⚠"
                    if row["Validated"] == "Partial"
                    else "✗"
                )
                lines.append(
                    f"    {status_symbol} {row['Evaluator']}: "
                    f"MAE={row['Mean_Abs_Error']:.3f}, "
                    f"RMSE={row['RMSE']:.3f}, "
                    f"Success={row['Strict_Success_Rate']:.2%}"
                )
                if row["Validated"] != "Yes":
                    lines.append(
                        f"       Issues: {row['Exact_Count']}/{row['N_Runs']} exact, "
                        f"{row['Poor_Count']} poor alignment"
                    )

        lines.append("")
        lines.append("TOP 3 PERFORMERS (by Mean Absolute Error):")
        top3 = self.validation_summary.nsmallest(3, "Mean_Abs_Error")
        for i, (_, row) in enumerate(top3.iterrows(), 1):
            lines.append(
                f"  {i}. {row['Evaluator']}: "
                f"MAE={row['Mean_Abs_Error']:.3f}, "
                f"Success={row['Strict_Success_Rate']:.2%}"
            )
        lines.append("")
        lines.append("BOTTOM 3 PERFORMERS (by Mean Absolute Error):")
        bottom3 = self.validation_summary.nlargest(3, "Mean_Abs_Error")
        for i, (_, row) in enumerate(bottom3.iterrows(), 1):
            lines.append(
                f"  {i}. {row['Evaluator']}: "
                f"MAE={row['Mean_Abs_Error']:.3f}, "
                f"Success={row['Strict_Success_Rate']:.2%}"
            )
        lines.append("")
        lines.append("=" * 80)

        summary_text = "\n".join(lines)
        print(summary_text)
        with open(self.output_dir / "validation_summary.txt", "w", encoding="utf-8") as f:
            f.write(summary_text)
        return summary_text

    def run_full_validation(self):
        print("\n" + "=" * 80)
        print("STARTING PSALM EVALUATOR VALIDATION ANALYSIS")
        print("=" * 80 + "\n")

        print("1. Loading control experiment results...")
        self.load_results()
        print("")

        print("2. Computing validation metrics...")
        self.compute_validation_metrics()
        print("   ✓ Validation metrics computed\n")

        print("3. Generating visualizations...")
        self.plot_score_heatmap()
        self.plot_absolute_error_by_evaluator()
        self.plot_expected_vs_actual_scatter()
        self.plot_alignment_distribution()
        self.plot_error_distribution_by_category()
        self.plot_validation_summary()
        self.plot_test_case_detail()
        print("")

        print("4. Exporting results...")
        self.export_results()
        print("")