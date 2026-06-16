from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from scipy import stats
from scipy.stats import (
    shapiro,
    levene,
    wilcoxon,
    ttest_rel,
)
from statsmodels.stats.anova import anova_lm
from statsmodels.formula.api import ols

warnings.filterwarnings("ignore")


class AdvancedStatisticalTests:
    """
    Advanced statistical tests for 2×2 factorial experiments:
    Language × Condition (e.g., Baseline/Finetuned, Finetuned/NPO, etc.).

    Handles arbitrary condition names via factor_map.
    """

    def __init__(
        self,
        comparator,
        factor_map: Optional[Dict[str, Tuple[str, str]]] = None,
        alpha: float = 0.05,
        equivalence_bounds: Tuple[float, float] = (-0.1, 0.1),
        verbose: bool = True,
    ):
        self.comparator = comparator
        self.alpha = alpha
        self.equivalence_bounds = equivalence_bounds
        self.verbose = verbose

        if factor_map is None:
            self.factor_map = self._infer_factors()
        else:
            self.factor_map = factor_map

        if len(self.factor_map) != len(self.comparator.model_names):
            raise ValueError(
                f"factor_map must cover all {len(self.comparator.model_names)} models"
            )

        self._attach_factors()

        # Auto-detect baseline vs treated conditions per language
        self._detect_unlearning_conditions()

        # Storage
        self.anova_results = {}
        self.paired_results = {}
        self.tost_results = {}
        self.contrast_results = {}
        self.effect_sizes = {}
        self.assumption_checks = {}

    @staticmethod
    def _safe_name(name: str) -> str:
        """
        Make a metric/category name safe for filenames:
        - replace slashes and backslashes with underscores
        - replace spaces with underscores
        - remove other obviously problematic characters
        """
        if not isinstance(name, str):
            name = str(name)
        bad_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        safe = name
        for ch in bad_chars:
            safe = safe.replace(ch, "_")
        safe = safe.replace(" ", "_")
        return safe

    # ------------------------------------------------------------------
    # Factor handling
    # ------------------------------------------------------------------

    def _infer_factors(self) -> Dict[str, Tuple[str, str]]:
        """Infer Language and Condition factors from model names."""
        factor_map = {}
        for name in self.comparator.model_names:
            name_lower = name.lower()

            # Language
            if (
                "english" in name_lower
                or "_en" in name_lower
                or name_lower.startswith("en")
            ):
                lang = "English"
            elif (
                "dutch" in name_lower
                or "_nl" in name_lower
                or name_lower.startswith("nl")
            ):
                lang = "Dutch"
            else:
                lang = "Unknown"

            # Condition / "unlearning"
            if (
                "baseline" in name_lower
                or "base" in name_lower
                or "_b" in name_lower
                or "control" in name_lower
            ):
                cond = "Baseline"
            elif "unlearn" in name_lower or "_u" in name_lower or "npo" in name_lower:
                cond = "Unlearned"
            else:
                cond = "Unknown"

            factor_map[name] = (lang, cond)

        if self.verbose:
            print("Inferred factor structure:")
            for model, (lang, cond) in factor_map.items():
                print(f"  {model}: Language={lang}, Condition={cond}")

        return factor_map

    def _attach_factors(self):
        """Add Language and Condition columns to comparator.data_long."""
        df = self.comparator.data_long.copy()
        df["Language"] = df["model"].map(lambda m: self.factor_map[m][0])
        df["Unlearning"] = df["model"].map(lambda m: self.factor_map[m][1])
        self.comparator.data_long = df

    def _detect_unlearning_conditions(self):
        """
        Auto-detect the two conditions per language.
        Stores mapping: {language: {"baseline": condition1, "treated": condition2}}.
        """
        df = self.comparator.data_long
        self.unlearning_map = {}

        for lang in df["Language"].unique():
            conditions = df[df["Language"] == lang]["Unlearning"].unique()
            if len(conditions) != 2:
                if self.verbose:
                    print(
                        f"[WARN] Language '{lang}' has {len(conditions)} conditions "
                        f"(expected 2)"
                    )
                continue

            baseline_keywords = ["baseline", "base", "control"]
            baseline_cond = None
            treated_cond = None

            for cond in conditions:
                if any(kw in cond.lower() for kw in baseline_keywords):
                    baseline_cond = cond
                else:
                    treated_cond = cond

            # Fallback: alphabetical ordering
            if baseline_cond is None:
                baseline_cond, treated_cond = sorted(conditions)

            self.unlearning_map[lang] = {
                "baseline": baseline_cond,
                "treated": treated_cond,
            }

        if self.verbose:
            print("\nDetected conditions per language:")
            for lang, conds in self.unlearning_map.items():
                print(
                    f"  {lang}: Baseline='{conds['baseline']}', "
                    f"Treated='{conds['treated']}'"
                )

    # ------------------------------------------------------------------
    # 1. TWO-WAY ANOVA WITH INTERACTION
    # ------------------------------------------------------------------

    def two_way_anova(
        self,
        analyze_split: str = "forget",
        parametric: bool = True,
    ) -> pd.DataFrame:
        """Two-way ANOVA (or rank-based ANOVA) for Language × Condition per metric."""
        df = self.comparator._split_selector(analyze_split)
        results = []

        for metric in df["metric"].unique():
            sub = df[df["metric"] == metric].copy()
            metric_name = sub["metric_clean"].iloc[0]

            if parametric:
                try:
                    formula = (
                        "score ~ C(Language) + C(Unlearning) + "
                        "C(Language):C(Unlearning)"
                    )
                    model = ols(formula, data=sub).fit()
                    anova_table = anova_lm(model, typ=2)

                    lang_f = anova_table.loc["C(Language)", "F"]
                    lang_p = anova_table.loc["C(Language)", "PR(>F)"]
                    unl_f = anova_table.loc["C(Unlearning)", "F"]
                    unl_p = anova_table.loc["C(Unlearning)", "PR(>F)"]
                    inter_f = anova_table.loc["C(Language):C(Unlearning)", "F"]
                    inter_p = anova_table.loc[
                        "C(Language):C(Unlearning)", "PR(>F)"
                    ]

                    ss_total = anova_table["sum_sq"].sum()
                    eta2_lang = anova_table.loc["C(Language)", "sum_sq"] / ss_total
                    eta2_unl = anova_table.loc["C(Unlearning)", "sum_sq"] / ss_total
                    eta2_inter = (
                        anova_table.loc["C(Language):C(Unlearning)", "sum_sq"]
                        / ss_total
                    )

                    def omega_squared(row, df_resid, ms_resid):
                        ss = row["sum_sq"]
                        df_ = row["df"]
                        return (ss - df_ * ms_resid) / (ss_total + ms_resid)

                    ms_resid = (
                        anova_table.loc["Residual", "sum_sq"]
                        / anova_table.loc["Residual", "df"]
                    )
                    df_resid = anova_table.loc["Residual", "df"]

                    omega2_lang = omega_squared(
                        anova_table.loc["C(Language)"], df_resid, ms_resid
                    )
                    omega2_unl = omega_squared(
                        anova_table.loc["C(Unlearning)"], df_resid, ms_resid
                    )
                    omega2_inter = omega_squared(
                        anova_table.loc["C(Language):C(Unlearning)"],
                        df_resid,
                        ms_resid,
                    )

                    results.append(
                        {
                            "Metric": metric_name,
                            "Split": analyze_split,
                            "Test": "Two-Way ANOVA",
                            "Language_F": lang_f,
                            "Language_p": lang_p,
                            "Language_sig": "Yes" if lang_p < self.alpha else "No",
                            "Language_eta2": eta2_lang,
                            "Language_omega2": omega2_lang,
                            "Unlearning_F": unl_f,
                            "Unlearning_p": unl_p,
                            "Unlearning_sig": "Yes" if unl_p < self.alpha else "No",
                            "Unlearning_eta2": eta2_unl,
                            "Unlearning_omega2": omega2_unl,
                            "Interaction_F": inter_f,
                            "Interaction_p": inter_p,
                            "Interaction_sig": "Yes" if inter_p < self.alpha else "No",
                            "Interaction_eta2": eta2_inter,
                            "Interaction_omega2": omega2_inter,
                        }
                    )

                except Exception as e:
                    if self.verbose:
                        print(f"[WARN] ANOVA failed for {metric_name}: {e}")
                    continue
            else:
                # Rank-based ANOVA
                try:
                    sub["rank"] = sub["score"].rank()
                    formula = (
                        "rank ~ C(Language) + C(Unlearning) + "
                        "C(Language):C(Unlearning)"
                    )
                    model = ols(formula, data=sub).fit()
                    anova_table = anova_lm(model, typ=2)

                    lang_f = anova_table.loc["C(Language)", "F"]
                    lang_p = anova_table.loc["C(Language)", "PR(>F)"]
                    unl_f = anova_table.loc["C(Unlearning)", "F"]
                    unl_p = anova_table.loc["C(Unlearning)", "PR(>F)"]
                    inter_f = anova_table.loc["C(Language):C(Unlearning)", "F"]
                    inter_p = anova_table.loc[
                        "C(Language):C(Unlearning)", "PR(>F)"
                    ]

                    results.append(
                        {
                            "Metric": metric_name,
                            "Split": analyze_split,
                            "Test": "ART-ANOVA (Rank-based)",
                            "Language_F": lang_f,
                            "Language_p": lang_p,
                            "Language_sig": "Yes" if lang_p < self.alpha else "No",
                            "Language_eta2": np.nan,
                            "Language_omega2": np.nan,
                            "Unlearning_F": unl_f,
                            "Unlearning_p": unl_p,
                            "Unlearning_sig": "Yes" if unl_p < self.alpha else "No",
                            "Unlearning_eta2": np.nan,
                            "Unlearning_omega2": np.nan,
                            "Interaction_F": inter_f,
                            "Interaction_p": inter_p,
                            "Interaction_sig": "Yes" if inter_p < self.alpha else "No",
                            "Interaction_eta2": np.nan,
                            "Interaction_omega2": np.nan,
                        }
                    )
                except Exception as e:
                    if self.verbose:
                        print(f"[WARN] ART-ANOVA failed for {metric_name}: {e}")
                    continue

        self.anova_results[analyze_split] = pd.DataFrame(results)
        return self.anova_results[analyze_split]

    # ------------------------------------------------------------------
    # 2. PAIRED TESTS (BASELINE VS TREATED)
    # ------------------------------------------------------------------

    def paired_tests(
        self,
        analyze_split: str = "forget",
        parametric: bool = False,
    ) -> pd.DataFrame:
        """Within-language paired tests: baseline vs treated."""
        df = self.comparator._split_selector(analyze_split)
        results = []

        for lang in self.unlearning_map.keys():
            lang_data = df[df["Language"] == lang].copy()

            baseline_cond = self.unlearning_map[lang]["baseline"]
            treated_cond = self.unlearning_map[lang]["treated"]

            baseline_models = lang_data[
                lang_data["Unlearning"] == baseline_cond
            ]["model"].unique()
            treated_models = lang_data[
                lang_data["Unlearning"] == treated_cond
            ]["model"].unique()

            if len(baseline_models) == 0 or len(treated_models) == 0:
                if self.verbose:
                    print(
                        f"[WARN] Skipping {lang}: missing baseline "
                        f"or treated model"
                    )
                continue

            baseline_model = baseline_models[0]
            treated_model = treated_models[0]

            for metric in df["metric"].unique():
                metric_name = (
                    df[df["metric"] == metric]["metric_clean"].iloc[0]
                )

                base_scores = (
                    lang_data[
                        (lang_data["model"] == baseline_model)
                        & (lang_data["metric"] == metric)
                    ][["ti_id", "score"]]
                    .rename(columns={"score": "baseline"})
                )

                treated_scores = (
                    lang_data[
                        (lang_data["model"] == treated_model)
                        & (lang_data["metric"] == metric)
                    ][["ti_id", "score"]]
                    .rename(columns={"score": "treated"})
                )

                paired = pd.merge(
                    base_scores, treated_scores, on="ti_id", how="inner"
                )

                if len(paired) < 3:
                    continue

                baseline_vals = paired["baseline"].values
                treated_vals = paired["treated"].values

                diff = treated_vals - baseline_vals
                mean_diff = np.mean(diff)

                d_paired = (
                    mean_diff / np.std(diff, ddof=1)
                    if np.std(diff, ddof=1) > 0
                    else np.nan
                )

                if parametric:
                    stat, p = ttest_rel(baseline_vals, treated_vals)
                    test_name = "Paired t-test"
                else:
                    stat, p = wilcoxon(baseline_vals, treated_vals)
                    test_name = "Wilcoxon signed-rank"

                results.append(
                    {
                        "Metric": metric_name,
                        "Split": analyze_split,
                        "Language": lang,
                        "Test": test_name,
                        "N_pairs": len(paired),
                        "Baseline_mean": np.mean(baseline_vals),
                        "Treated_mean": np.mean(treated_vals),
                        "Mean_diff": mean_diff,
                        "TestStat": stat,
                        "p_value": p,
                        "Significant": "Yes" if p < self.alpha else "No",
                        "Cohen_d_paired": d_paired,
                    }
                )

        self.paired_results[analyze_split] = pd.DataFrame(results)
        return self.paired_results[analyze_split]

    # ------------------------------------------------------------------
    # 3. TOST EQUIVALENCE TESTS
    # ------------------------------------------------------------------

    def tost_equivalence_tests(
        self,
        analyze_split: str = "retain",
        target_categories: Optional[List[str]] = None,
        target_metrics: Optional[List[str]] = None,
        exclude_categories: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        TOST equivalence tests for retain set.

        Tests whether baseline and treated models are equivalent within
        equivalence_bounds on specified metrics.
        """
        df = self.comparator._split_selector(analyze_split)

        # Determine which metrics to test
        if target_metrics is not None:
            metrics_to_test = target_metrics
        elif target_categories is not None:
            metrics_to_test = []
            for cat in target_categories:
                metrics_to_test.extend(
                    self.comparator.metric_categories.get(cat, [])
                )
        else:
            metrics_to_test = []
            exclude_cats = exclude_categories or []

            for cat, metrics in self.comparator.metric_categories.items():
                if cat not in exclude_cats:
                    metrics_to_test.extend(metrics)

            if self.verbose:
                tested_cats = [
                    cat
                    for cat in self.comparator.metric_categories.keys()
                    if cat not in exclude_cats
                ]
                print(
                    f"   TOST: Testing equivalence for categories: "
                    f"{tested_cats}"
                )

        # Remove duplicates while preserving order
        metrics_to_test = list(dict.fromkeys(metrics_to_test))

        # Filter metrics that exist
        metrics_to_test = [
            m for m in metrics_to_test if m in df["metric"].values
        ]

        if not metrics_to_test:
            if self.verbose:
                print("[WARN] No metrics found for TOST. Skipping.")
            self.tost_results[analyze_split] = pd.DataFrame()
            return self.tost_results[analyze_split]

        results = []
        lower, upper = self.equivalence_bounds

        for lang in self.unlearning_map.keys():
            lang_data = df[df["Language"] == lang].copy()

            baseline_cond = self.unlearning_map[lang]["baseline"]
            treated_cond = self.unlearning_map[lang]["treated"]

            baseline_models = lang_data[
                lang_data["Unlearning"] == baseline_cond
            ]["model"].unique()
            treated_models = lang_data[
                lang_data["Unlearning"] == treated_cond
            ]["model"].unique()

            if len(baseline_models) == 0 or len(treated_models) == 0:
                continue

            baseline_model = baseline_models[0]
            treated_model = treated_models[0]

            for metric in metrics_to_test:
                if metric not in df["metric"].values:
                    continue

                sub = df[df["metric"] == metric]
                metric_name = sub["metric_clean"].iloc[0]
                metric_category = sub["category"].iloc[0]

                base_scores = (
                    lang_data[
                        (lang_data["model"] == baseline_model)
                        & (lang_data["metric"] == metric)
                    ]["score"]
                    .dropna()
                    .values
                )

                treated_scores = (
                    lang_data[
                        (lang_data["model"] == treated_model)
                        & (lang_data["metric"] == metric)
                    ]["score"]
                    .dropna()
                    .values
                )

                if len(base_scores) < 3 or len(treated_scores) < 3:
                    continue

                mean_diff = np.mean(treated_scores) - np.mean(base_scores)
                se_diff = np.sqrt(
                    np.var(base_scores, ddof=1) / len(base_scores)
                    + np.var(treated_scores, ddof=1) / len(treated_scores)
                )

                if se_diff == 0:
                    continue

                df_welch = (
                    (
                        np.var(base_scores, ddof=1) / len(base_scores)
                        + np.var(treated_scores, ddof=1) / len(treated_scores)
                    )
                    ** 2
                ) / (
                    (np.var(base_scores, ddof=1) / len(base_scores)) ** 2
                    / (len(base_scores) - 1)
                    + (np.var(treated_scores, ddof=1) / len(treated_scores))
                    ** 2
                    / (len(treated_scores) - 1)
                )

                t1 = (mean_diff - lower) / se_diff
                p1 = 1 - stats.t.cdf(t1, df_welch)

                t2 = (mean_diff - upper) / se_diff
                p2 = stats.t.cdf(t2, df_welch)

                tost_p = max(p1, p2)
                equivalent = "Yes" if tost_p < self.alpha else "No"

                results.append(
                    {
                        "Metric": metric_name,
                        "Category": metric_category,
                        "Split": analyze_split,
                        "Language": lang,
                        "Test": "TOST",
                        "Equivalence_bounds": f"[{lower}, {upper}]",
                        "Baseline_mean": np.mean(base_scores),
                        "Treated_mean": np.mean(treated_scores),
                        "Mean_diff": mean_diff,
                        "SE_diff": se_diff,
                        "TOST_p": tost_p,
                        "Equivalent": equivalent,
                        "t1": t1,
                        "p1": p1,
                        "t2": t2,
                        "p2": p2,
                    }
                )

        self.tost_results[analyze_split] = pd.DataFrame(results)

        if self.verbose and len(self.tost_results[analyze_split]) > 0:
            summary = (
                self.tost_results[analyze_split]
                .groupby("Category")["Equivalent"]
                .apply(lambda x: f"{(x == 'Yes').sum()}/{len(x)}")
            )
            print(f"   TOST equivalence by category:")
            for cat, counts in summary.items():
                print(f"     {cat}: {counts}")

        return self.tost_results[analyze_split]

    # ------------------------------------------------------------------
    # 4. DIFFERENTIAL EFFECT CONTRASTS (ALL CATEGORIES)
    # ------------------------------------------------------------------

    def differential_effect_contrasts(
        self,
        analyze_split: str = "forget",
    ) -> pd.DataFrame:
        """
        Tests whether the treated condition reduces certain categories more than
        others, relative to the baseline condition.
        Compares all categories pairwise within each language.
        """
        df = self.comparator._split_selector(analyze_split)
        results = []

        categories = list(self.comparator.metric_categories.keys())

        for lang in self.unlearning_map.keys():
            lang_data = df[df["Language"] == lang].copy()

            baseline_cond = self.unlearning_map[lang]["baseline"]
            treated_cond = self.unlearning_map[lang]["treated"]

            baseline_models = lang_data[
                lang_data["Unlearning"] == baseline_cond
            ]["model"].unique()
            treated_models = lang_data[
                lang_data["Unlearning"] == treated_cond
            ]["model"].unique()

            if len(baseline_models) == 0 or len(treated_models) == 0:
                continue

            baseline_model = baseline_models[0]
            treated_model = treated_models[0]

            category_deltas = {}

            for cat in categories:
                cat_metrics = self.comparator.metric_categories.get(cat, [])

                def get_category_scores(model_name, metrics):
                    sub = lang_data[
                        (lang_data["model"] == model_name)
                        & (lang_data["metric"].isin(metrics))
                    ]
                    return sub.groupby("ti_id")["score"].mean()

                cat_base = get_category_scores(baseline_model, cat_metrics)
                cat_treated = get_category_scores(treated_model, cat_metrics)

                cat_paired = pd.DataFrame(
                    {"base": cat_base, "treated": cat_treated}
                ).dropna()

                if len(cat_paired) >= 3:
                    category_deltas[cat] = cat_paired["base"] - cat_paired[
                        "treated"
                    ]

            for i, cat1 in enumerate(categories):
                for cat2 in categories[i + 1 :]:
                    if cat1 not in category_deltas or cat2 not in category_deltas:
                        continue

                    delta1 = category_deltas[cat1]
                    delta2 = category_deltas[cat2]

                    common_ids = set(delta1.index) & set(delta2.index)
                    if len(common_ids) < 3:
                        continue

                    delta1 = delta1.loc[list(common_ids)]
                    delta2 = delta2.loc[list(common_ids)]

                    stat, p = ttest_rel(delta1, delta2)

                    mean_delta1 = delta1.mean()
                    mean_delta2 = delta2.mean()

                    diff_delta = delta1 - delta2
                    d_contrast = (
                        diff_delta.mean() / diff_delta.std(ddof=1)
                        if diff_delta.std(ddof=1) > 0
                        else np.nan
                    )

                    results.append(
                        {
                            "Language": lang,
                            "Split": analyze_split,
                            "Category1": cat1,
                            "Category2": cat2,
                            "Test": "Differential Effect Contrast",
                            "N_samples": len(common_ids),
                            f"{cat1}_reduction_mean": mean_delta1,
                            f"{cat2}_reduction_mean": mean_delta2,
                            "Difference": mean_delta1 - mean_delta2,
                            "TestStat_t": stat,
                            "p_value": p,
                            "Significant": "Yes"
                            if p < self.alpha
                            else "No",
                            "Cohen_d": d_contrast,
                            "Interpretation": (
                                f"Category '{cat1}' reduced more than '{cat2}'"
                                if (p < self.alpha and mean_delta1 > mean_delta2)
                                else "No selective category difference"
                            ),
                        }
                    )

        self.contrast_results[analyze_split] = pd.DataFrame(results)
        return self.contrast_results[analyze_split]

    # ------------------------------------------------------------------
    # 5. ENHANCED EFFECT SIZES
    # ------------------------------------------------------------------

    def compute_enhanced_effect_sizes(
        self,
        analyze_split: str = "forget",
    ) -> pd.DataFrame:
        """Compute Hedge's g, Cliff's delta, Glass's delta for all pairwise comparisons."""
        df = self.comparator._split_selector(analyze_split)
        results = []

        models = df["model"].unique()

        for metric in df["metric"].unique():
            metric_name = (
                df[df["metric"] == metric]["metric_clean"].iloc[0]
            )

            for i in range(len(models)):
                for j in range(i + 1, len(models)):
                    m1, m2 = models[i], models[j]

                    scores1 = (
                        df[
                            (df["model"] == m1) & (df["metric"] == metric)
                        ]["score"]
                        .dropna()
                        .values
                    )
                    scores2 = (
                        df[
                            (df["model"] == m2) & (df["metric"] == metric)
                        ]["score"]
                        .dropna()
                        .values
                    )

                    if len(scores1) < 2 or len(scores2) < 2:
                        continue

                    n1, n2 = len(scores1), len(scores2)
                    m1_mean, m2_mean = np.mean(scores1), np.mean(scores2)
                    s1, s2 = (
                        np.std(scores1, ddof=1),
                        np.std(scores2, ddof=1),
                    )

                    s_pooled = np.sqrt(
                        ((n1 - 1) * s1**2 + (n2 - 1) * s2**2)
                        / (n1 + n2 - 2)
                    )
                    cohens_d = (
                        (m1_mean - m2_mean) / s_pooled
                        if s_pooled > 0
                        else np.nan
                    )

                    correction = 1 - (3 / (4 * (n1 + n2) - 9))
                    hedges_g = cohens_d * correction

                    glass_delta = (
                        (m1_mean - m2_mean) / s2 if s2 > 0 else np.nan
                    )

                    def cliffs_delta(x, y):
                        n1_, n2_ = len(x), len(y)
                        dominance = sum(
                            sum(
                                1 if xi > yi else -1 if xi < yi else 0
                                for yi in y
                            )
                            for xi in x
                        )
                        return dominance / (n1_ * n2_)

                    cliff_d = cliffs_delta(scores1, scores2)

                    def interpret_d(d_):
                        ad = abs(d_)
                        if ad < 0.2:
                            return "negligible"
                        elif ad < 0.5:
                            return "small"
                        elif ad < 0.8:
                            return "medium"
                        else:
                            return "large"

                    def interpret_cliff(c_):
                        ac = abs(c_)
                        if ac < 0.147:
                            return "negligible"
                        elif ac < 0.33:
                            return "small"
                        elif ac < 0.474:
                            return "medium"
                        else:
                            return "large"

                    results.append(
                        {
                            "Metric": metric_name,
                            "Split": analyze_split,
                            "Model1": m1,
                            "Model2": m2,
                            "N1": n1,
                            "N2": n2,
                            "Mean1": m1_mean,
                            "Mean2": m2_mean,
                            "Cohen_d": cohens_d,
                            "Hedge_g": hedges_g,
                            "Glass_delta": glass_delta,
                            "Cliff_delta": cliff_d,
                            "d_interpretation": interpret_d(cohens_d),
                            "cliff_interpretation": interpret_cliff(cliff_d),
                        }
                    )

        self.effect_sizes[analyze_split] = pd.DataFrame(results)
        return self.effect_sizes[analyze_split]

    # ------------------------------------------------------------------
    # 6. ASSUMPTION CHECKS
    # ------------------------------------------------------------------

    def check_assumptions(
        self,
        analyze_split: str = "forget",
    ) -> pd.DataFrame:
        """Check normality and homogeneity assumptions per metric."""
        df = self.comparator._split_selector(analyze_split)
        results = []

        for metric in df["metric"].unique():
            metric_name = (
                df[df["metric"] == metric]["metric_clean"].iloc[0]
            )
            sub = df[df["metric"] == metric]

            normality_pass = True
            for model in sub["model"].unique():
                scores = sub[sub["model"] == model]["score"].dropna().values
                if len(scores) >= 3:
                    _, p = shapiro(scores)
                    if p < 0.05:
                        normality_pass = False
                        break

            groups = [
                sub[sub["model"] == m]["score"].dropna().values
                for m in sub["model"].unique()
            ]
            groups = [g for g in groups if len(g) >= 2]

            if len(groups) >= 2:
                _, p_levene = levene(*groups)
                homogeneity_pass = p_levene >= 0.05
            else:
                p_levene = np.nan
                homogeneity_pass = False

            recommendation = (
                "Parametric OK"
                if (normality_pass and homogeneity_pass)
                else "Use non-parametric"
            )

            results.append(
                {
                    "Metric": metric_name,
                    "Split": analyze_split,
                    "Normality_pass": "Yes"
                    if normality_pass
                    else "No",
                    "Homogeneity_pass": "Yes"
                    if homogeneity_pass
                    else "No",
                    "Levene_p": p_levene,
                    "Recommendation": recommendation,
                }
            )

        self.assumption_checks[analyze_split] = pd.DataFrame(results)
        return self.assumption_checks[analyze_split]

    # ------------------------------------------------------------------
    # VISUALIZATION
    # ------------------------------------------------------------------

    def plot_interaction(
            self,
            out_dir: Union[str, Path],
            analyze_split: str = "forget",
            figsize_per_plot: Tuple[int, int] = (12, 8),
            create_overview: bool = True,
            separate_plots: bool = False,
    ):
        """
        Interaction plots for ALL categories.

        Parameters
        ----------
        separate_plots : bool
            If True, saves one PNG per metric.
            If False, keeps the combined grids per category.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        df = self.comparator._split_selector(analyze_split)

        # 1. Per-category plots
        for cat_name, metrics in self.comparator.metric_categories.items():
            available_metrics = [m for m in metrics if m in df["metric"].values]
            if not available_metrics:
                continue

            safe_cat = self._safe_name(cat_name)

            if separate_plots:
                # One figure per metric
                for metric in available_metrics:
                    sub = df[df["metric"] == metric].copy()
                    metric_name = sub["metric_clean"].iloc[0]
                    safe_metric = self._safe_name(metric_name)

                    fig, ax = plt.subplots(figsize=figsize_per_plot)
                    means = (
                        sub.groupby(["Language", "Unlearning"])["score"]
                        .mean()
                        .reset_index()
                    )

                    for lang in means["Language"].unique():
                        lang_means = means[means["Language"] == lang]
                        ax.plot(
                            lang_means["Unlearning"],
                            lang_means["score"],
                            marker="o",
                            markersize=10,
                            linewidth=2.5,
                            label=lang,
                        )

                    ax.set_title(
                        f"{metric_name} [{cat_name}]",
                        fontsize=12,
                        fontweight="bold",
                    )
                    ax.set_xlabel("Condition", fontsize=11)
                    ax.set_ylabel("Mean Score", fontsize=11)
                    ax.legend(loc="best", fontsize=10)
                    ax.grid(True, alpha=0.3, linestyle="--")
                    ax.set_ylim([0, 1.05])

                    fname = f"interaction_{analyze_split}_{safe_cat}_{safe_metric}.png"
                    fpath = out_dir / fname
                    plt.tight_layout()
                    plt.savefig(fpath, dpi=300, bbox_inches="tight")
                    plt.close()

                    if self.verbose:
                        print(f"✓ Saved {fpath}")
            else:
                # Combined grid per category
                n_metrics = len(available_metrics)
                n_cols = min(3, n_metrics)
                n_rows = int(np.ceil(n_metrics / n_cols))

                fig_width = 4 * n_cols + 2
                fig_height = 3 * n_rows + 1

                fig, axes = plt.subplots(
                    n_rows, n_cols, figsize=(fig_width, fig_height)
                )
                if n_metrics == 1:
                    axes = np.array([axes])
                axes = axes.flatten()

                for i, metric in enumerate(available_metrics):
                    ax = axes[i]
                    sub = df[df["metric"] == metric].copy()
                    metric_name = sub["metric_clean"].iloc[0]

                    means = (
                        sub.groupby(["Language", "Unlearning"])["score"]
                        .mean()
                        .reset_index()
                    )

                    for lang in means["Language"].unique():
                        lang_means = means[means["Language"] == lang]
                        ax.plot(
                            lang_means["Unlearning"],
                            lang_means["score"],
                            marker="o",
                            markersize=10,
                            linewidth=2.5,
                            label=lang,
                        )

                    ax.set_title(metric_name, fontsize=12, fontweight="bold")
                    ax.set_xlabel("Condition", fontsize=11)
                    ax.set_ylabel("Mean Score", fontsize=11)
                    ax.legend(loc="best", fontsize=10)
                    ax.grid(True, alpha=0.3, linestyle="--")
                    ax.set_ylim([0, 1.05])

                for j in range(n_metrics, len(axes)):
                    axes[j].axis("off")

                plt.suptitle(
                    f"{cat_name} Metrics: Language × Condition Interaction",
                    fontsize=14,
                    fontweight="bold",
                    y=0.995,
                )
                plt.tight_layout()

                fname = f"interaction_{analyze_split}_{safe_cat}.png"
                fpath = out_dir / fname
                plt.savefig(fpath, dpi=300, bbox_inches="tight")
                plt.close()

                if self.verbose:
                    print(f"✓ Saved {fpath}")

        # 2. Overview plot (optional)
        if create_overview:
            all_metrics = [m for m in df["metric"].unique()]
            n = len(all_metrics)
            n_cols = 4
            n_rows = int(np.ceil(n / n_cols))

            fig, axes = plt.subplots(
                n_rows, n_cols, figsize=(20, 4 * n_rows)
            )
            axes = axes.flatten()

            for i, metric in enumerate(all_metrics):
                ax = axes[i]
                sub = df[df["metric"] == metric].copy()
                metric_name = sub["metric_clean"].iloc[0]
                cat_name = sub["category"].iloc[0]

                means = (
                    sub.groupby(["Language", "Unlearning"])["score"]
                    .mean()
                    .reset_index()
                )

                for lang in means["Language"].unique():
                    lang_means = means[means["Language"] == lang]
                    ax.plot(
                        lang_means["Unlearning"],
                        lang_means["score"],
                        marker="o",
                        markersize=8,
                        linewidth=2,
                        label=lang,
                    )

                ax.set_title(
                    f"{metric_name}\n[{cat_name}]",
                    fontsize=9,
                )
                ax.set_xlabel("")
                ax.set_ylabel("Score", fontsize=8)
                ax.legend(fontsize=7)
                ax.grid(True, alpha=0.3)
                ax.tick_params(labelsize=8)

            for j in range(i + 1, len(axes)):
                axes[j].axis("off")

            plt.suptitle(
                f"Overview: All Metrics ({analyze_split.title()} Set)",
                fontsize=16,
                fontweight="bold",
            )
            plt.tight_layout()
            fpath = out_dir / f"interaction_overview_{analyze_split}.png"
            plt.savefig(fpath, dpi=300, bbox_inches="tight")
            plt.close()

            if self.verbose:
                print(f"✓ Saved overview: {fpath}")

    def plot_differential_effects(
        self,
        out_dir: Union[str, Path],
        analyze_split: str = "forget",
        figsize: Tuple[int, int] = (16, 6),
        show_only_significant: bool = False,
        style: str = "grouped",  # "grouped", "heatmap", or "both"
    ):
        """
        Publication-ready differential effects visualization.

        style:
            - "grouped": bar plots per language
            - "heatmap": category-by-category heatmap with shared color scale
            - "both": both visualizations
        """
        if (
            analyze_split not in self.contrast_results
            or len(self.contrast_results[analyze_split]) == 0
        ):
            if self.verbose:
                print("[WARN] No differential effects to plot")
            return

        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        df = self.contrast_results[analyze_split].copy()

        if show_only_significant:
            df = df[df["Significant"] == "Yes"].copy()
            if len(df) == 0:
                if self.verbose:
                    print(
                        "[WARN] No significant differential effects to plot"
                    )
                return

        if style in ["grouped", "both"]:
            self._plot_differential_grouped(
                df, out_dir, analyze_split, figsize
            )

        if style in ["heatmap", "both"]:
            self._plot_differential_heatmap(df, out_dir, analyze_split)

    def _plot_differential_grouped(
            self,
            df: pd.DataFrame,
            out_dir: Path,
            analyze_split: str,
            figsize: Tuple[int, int],
    ):
        """Grouped bar plot version of differential effects."""
        languages = df["Language"].unique()
        n_langs = len(languages)

        colors = {
            "cat1": "#2E86AB",
            "cat2": "#A23B72",
            "significant": "#F18F01",
        }

        fig, axes = plt.subplots(
            n_langs, 1, figsize=(figsize[0], figsize[1] * n_langs), squeeze=False
        )
        axes = axes.flatten()

        for idx, lang in enumerate(languages):
            ax = axes[idx]
            lang_df = df[df["Language"] == lang].copy()

            if len(lang_df) == 0:
                ax.text(
                    0.5,
                    0.5,
                    f"No data for {lang}",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
                ax.set_xlim([0, 1])
                ax.set_ylim([0, 1])
                continue

            lang_df["comparison"] = lang_df.apply(
                lambda row: f"{row['Category1']}\nvs\n{row['Category2']}",
                axis=1,
            )

            x = np.arange(len(lang_df))
            width = 0.38

            bars_data = []
            for _, row in lang_df.iterrows():
                cat1 = row["Category1"]
                cat2 = row["Category2"]
                val1 = row.get(f"{cat1}_reduction_mean", 0)
                val2 = row.get(f"{cat2}_reduction_mean", 0)
                bars_data.append((val1, val2))

            bars_data = np.array(bars_data)

            ax.bar(
                x - width / 2,
                bars_data[:, 0],
                width,
                label="Category 1 (left)",
                color=colors["cat1"],
                alpha=0.85,
                edgecolor="black",
                linewidth=1.2,
            )

            ax.bar(
                x + width / 2,
                bars_data[:, 1],
                width,
                label="Category 2 (right)",
                color=colors["cat2"],
                alpha=0.85,
                edgecolor="black",
                linewidth=1.2,
            )

            ax.set_xlabel(
                "Category Pair Comparison", fontsize=12, fontweight="bold"
            )
            ax.set_ylabel(
                "Mean Reduction\n(Baseline − Treated)",
                fontsize=12,
                fontweight="bold",
            )
            ax.set_title(
                f"{lang}: Differential Effects Across Categories",
                fontsize=14,
                fontweight="bold",
                pad=15,
            )
            ax.set_xticks(x)
            ax.set_xticklabels(
                lang_df["comparison"],
                fontsize=9,
                rotation=0,
                ha="center",
            )
            ax.legend(loc="upper right", fontsize=10, framealpha=0.95)
            ax.grid(True, axis="y", alpha=0.3, linestyle="--", linewidth=0.8)
            ax.axhline(0, color="black", linewidth=1.2, linestyle="-", zorder=1)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

            for plot_idx, (_, row) in enumerate(lang_df.iterrows()):
                y_max = max(bars_data[plot_idx, 0], bars_data[plot_idx, 1])
                y_min = min(bars_data[plot_idx, 0], bars_data[plot_idx, 1])
                y_range = ax.get_ylim()[1] - ax.get_ylim()[0]

                if row["Significant"] == "Yes":
                    p_val = row["p_value"]

                    if p_val < 0.001:
                        sig_str = "***"
                    elif p_val < 0.01:
                        sig_str = "**"
                    elif p_val < 0.05:
                        sig_str = "*"
                    else:
                        sig_str = ""

                    bracket_y = y_max + 0.03 * y_range
                    ax.plot(
                        [plot_idx - width / 2, plot_idx + width / 2],
                        [bracket_y, bracket_y],
                        "k-",
                        linewidth=1.5,
                        zorder=10,
                    )

                    ax.text(
                        plot_idx,
                        bracket_y + 0.015 * y_range,
                        f"{sig_str}\np={p_val:.3g}",
                        ha="center",
                        va="bottom",
                        fontsize=8,
                        fontweight="bold",
                        bbox=dict(
                            boxstyle="round,pad=0.25",
                            facecolor=colors["significant"],
                            alpha=0.6,
                            edgecolor="black",
                            linewidth=0.8,
                        ),
                        zorder=11,
                    )

                if "Cohen_d" in row and pd.notna(row["Cohen_d"]):
                    ax.text(
                        plot_idx,
                        y_min - 0.05 * y_range,
                        f"d={row['Cohen_d']:.2f}",
                        ha="center",
                        va="top",
                        fontsize=8,
                        style="italic",
                        color="#555555",
                    )

        plt.tight_layout()
        fpath = out_dir / f"differential_effects_grouped_{analyze_split}.png"
        plt.savefig(fpath, dpi=300, bbox_inches="tight")
        plt.close()

        if self.verbose:
            print(f"✓ Saved grouped plot: {fpath}")

    def _plot_differential_heatmap(
            self,
            df: pd.DataFrame,
            out_dir: Path,
            analyze_split: str,
    ):
        """Heatmap showing pairwise category differences with shared scale."""
        languages = df["Language"].unique()
        n_langs = len(languages)

        if len(df) == 0:
            return

        global_vmax = np.abs(df["Difference"].dropna()).max()
        if not np.isfinite(global_vmax) or global_vmax == 0:
            global_vmax = 1.0
        else:
            global_vmax = min(global_vmax, 1.0)

        fig, axes = plt.subplots(
            1, n_langs, figsize=(8 * n_langs, 7), squeeze=False
        )
        axes = axes.flatten()

        for idx, lang in enumerate(languages):
            ax = axes[idx]
            lang_df = df[df["Language"] == lang].copy()

            if len(lang_df) == 0:
                ax.text(
                    0.5,
                    0.5,
                    f"No data for {lang}",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
                continue

            all_cats = sorted(
                set(lang_df["Category1"].unique())
                | set(lang_df["Category2"].unique())
            )

            n_cats = len(all_cats)
            diff_matrix = np.zeros((n_cats, n_cats))
            sig_matrix = np.zeros((n_cats, n_cats), dtype=bool)

            cat_to_idx = {cat: i for i, cat in enumerate(all_cats)}

            for _, row in lang_df.iterrows():
                i = cat_to_idx[row["Category1"]]
                j = cat_to_idx[row["Category2"]]

                diff = row["Difference"]
                diff_matrix[i, j] = diff
                diff_matrix[j, i] = -diff

                if row["Significant"] == "Yes":
                    sig_matrix[i, j] = True
                    sig_matrix[j, i] = True

            im = ax.imshow(
                diff_matrix,
                cmap="RdBu_r",
                vmin=-global_vmax,
                vmax=global_vmax,
                aspect="auto",
            )

            cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label(
                "Differential Effect\n(positive = row > column)",
                fontsize=10,
                fontweight="bold",
            )

            for i in range(n_cats):
                for j in range(n_cats):
                    if i == j:
                        continue

                    text_val = f"{diff_matrix[i, j]:.3f}"
                    if sig_matrix[i, j]:
                        text_val += "\n*"

                    text_color = (
                        "white"
                        if abs(diff_matrix[i, j]) > global_vmax * 0.5
                        else "black"
                    )

                    ax.text(
                        j,
                        i,
                        text_val,
                        ha="center",
                        va="center",
                        fontsize=8,
                        fontweight="bold" if sig_matrix[i, j] else "normal",
                        color=text_color,
                    )

            ax.set_xticks(np.arange(n_cats))
            ax.set_yticks(np.arange(n_cats))
            ax.set_xticklabels(
                all_cats, rotation=45, ha="right", fontsize=10
            )
            ax.set_yticklabels(all_cats, fontsize=10)

            ax.set_title(
                f"{lang}: Category Differential Effects\n"
                f"(* = significant, α={self.alpha})",
                fontsize=12,
                fontweight="bold",
                pad=10,
            )

            ax.set_xticks(np.arange(n_cats) - 0.5, minor=True)
            ax.set_yticks(np.arange(n_cats) - 0.5, minor=True)
            ax.grid(which="minor", color="gray", linestyle="-", linewidth=1)

        plt.tight_layout()
        fpath = out_dir / f"differential_effects_heatmap_{analyze_split}.png"
        plt.savefig(fpath, dpi=300, bbox_inches="tight")
        plt.close()

        if self.verbose:
            print(f"✓ Saved heatmap: {fpath}")

    # ------------------------------------------------------------------
    # EXPORT
    # ------------------------------------------------------------------

    def export_all_results(self, out_dir: Union[str, Path]):
        """Export all test results to CSV and Excel."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        for name, results_dict in [
            ("anova", self.anova_results),
            ("paired", self.paired_results),
            ("tost", self.tost_results),
            ("contrasts", self.contrast_results),
            ("effect_sizes", self.effect_sizes),
            ("assumptions", self.assumption_checks),
        ]:
            for split, df in results_dict.items():
                if len(df) > 0:
                    df.to_csv(out_dir / f"{name}_{split}.csv", index=False)

        try:
            with pd.ExcelWriter(
                out_dir / "advanced_statistics.xlsx", engine="openpyxl"
            ) as writer:
                all_splits = set(
                    list(self.anova_results.keys())
                    + list(self.paired_results.keys())
                    + list(self.tost_results.keys())
                    + list(self.contrast_results.keys())
                    + list(self.effect_sizes.keys())
                    + list(self.assumption_checks.keys())
                )
                for split in all_splits:
                    if split in self.anova_results and len(
                        self.anova_results[split]
                    ) > 0:
                        self.anova_results[split].to_excel(
                            writer,
                            sheet_name=f"ANOVA_{split}",
                            index=False,
                        )
                    if split in self.paired_results and len(
                        self.paired_results[split]
                    ) > 0:
                        self.paired_results[split].to_excel(
                            writer,
                            sheet_name=f"Paired_{split}",
                            index=False,
                        )
                    if split in self.tost_results and len(
                        self.tost_results[split]
                    ) > 0:
                        self.tost_results[split].to_excel(
                            writer,
                            sheet_name=f"TOST_{split}",
                            index=False,
                        )
                    if split in self.contrast_results and len(
                        self.contrast_results[split]
                    ) > 0:
                        self.contrast_results[split].to_excel(
                            writer,
                            sheet_name=f"Contrast_{split}",
                            index=False,
                        )
                    if split in self.effect_sizes and len(
                        self.effect_sizes[split]
                    ) > 0:
                        self.effect_sizes[split].to_excel(
                            writer,
                            sheet_name=f"EffectSizes_{split}",
                            index=False,
                        )
                    if split in self.assumption_checks and len(
                        self.assumption_checks[split]
                    ) > 0:
                        self.assumption_checks[split].to_excel(
                            writer,
                            sheet_name=f"Assumptions_{split}",
                            index=False,
                        )
        except Exception as e:
            if self.verbose:
                print(f"[WARN] Excel export failed: {e}")

        if self.verbose:
            print(f"✓ Exported advanced statistics to {out_dir}")

    # ------------------------------------------------------------------
    # FULL PIPELINE
    # ------------------------------------------------------------------

    def run_full_analysis(
        self,
        out_dir: Union[str, Path] = "advanced_stats_output",
        test_splits: List[str] = ["forget", "retain"],
        parametric: bool = False,
    ):
        """Run complete advanced statistical analysis pipeline."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        if self.verbose:
            print("\n" + "=" * 80)
            print("ADVANCED STATISTICAL ANALYSIS")
            print("=" * 80 + "\n")

        for split in test_splits:
            if self.verbose:
                print(f"\n{'=' * 60}")
                print(f"ANALYZING: {split.upper()} SET")
                print(f"{'=' * 60}\n")

            if self.verbose:
                print("1) Checking parametric assumptions...")
            self.check_assumptions(analyze_split=split)

            if self.verbose:
                print(
                    "2) Running two-way ANOVA (Language × Condition)..."
                )
            self.two_way_anova(analyze_split=split, parametric=parametric)

            if self.verbose:
                print(
                    "3) Running paired tests (baseline vs treated per language)..."
                )
            self.paired_tests(analyze_split=split, parametric=parametric)

            if split == "retain":
                if self.verbose:
                    print("4) Running TOST equivalence tests...")
                self.tost_equivalence_tests(analyze_split=split)

            if split == "forget":
                if self.verbose:
                    print(
                        "5) Computing differential effects (all categories)..."
                    )
                self.differential_effect_contrasts(analyze_split=split)

            if self.verbose:
                print("6) Computing enhanced effect sizes...")
            self.compute_enhanced_effect_sizes(analyze_split=split)

            if self.verbose:
                print("7) Generating plots...")
            # Use separate_plots=True to produce one PNG per metric
            self.plot_interaction(
                out_dir=out_dir,
                analyze_split=split,
                separate_plots=True,
            )
            if split == "forget":
                self.plot_differential_effects(
                    out_dir=out_dir,
                    analyze_split=split,
                    style="both",
                )

        if self.verbose:
            print("\n8) Exporting results...")
        self.export_all_results(out_dir=out_dir)

        if self.verbose:
            print("\n" + "=" * 80)
            print("SUMMARY")
            print("=" * 80)
            self._print_summary()
            print(f"\n✓ All results saved to: {out_dir}")

    def _print_summary(self):
        """Print key findings summary."""
        for split in self.anova_results.keys():
            print(f"\n{split.upper()} SET:")

            if split in self.anova_results:
                anova_df = self.anova_results[split]
                sig_lang = (
                    anova_df["Language_sig"].value_counts().get("Yes", 0)
                )
                sig_unl = (
                    anova_df["Unlearning_sig"].value_counts().get("Yes", 0)
                )
                sig_inter = (
                    anova_df["Interaction_sig"].value_counts().get("Yes", 0)
                )

                print("  Significant main effects:")
                print(f"    Language: {sig_lang}/{len(anova_df)} metrics")
                print(f"    Condition: {sig_unl}/{len(anova_df)} metrics")
                print(
                    f"    Interaction: {sig_inter}/{len(anova_df)} metrics"
                )

            if split in self.paired_results:
                paired_df = self.paired_results[split]
                sig_paired = (
                    paired_df["Significant"].value_counts().get("Yes", 0)
                )
                print(
                    f"  Significant paired differences: "
                    f"{sig_paired}/{len(paired_df)}"
                )

            if split in self.tost_results:
                tost_df = self.tost_results[split]
                if len(tost_df) > 0 and "Equivalent" in tost_df.columns:
                    equiv = (
                        tost_df["Equivalent"]
                        .value_counts()
                        .get("Yes", 0)
                    )
                    print(
                        f"  Equivalent (TOST): "
                        f"{equiv}/{len(tost_df)} tests"
                    )

                    if "Category" in tost_df.columns:
                        print("    By category:")
                        for cat in tost_df["Category"].unique():
                            cat_df = tost_df[tost_df["Category"] == cat]
                            cat_equiv = (
                                cat_df["Equivalent"]
                                .value_counts()
                                .get("Yes", 0)
                            )
                            print(
                                f"      {cat}: "
                                f"{cat_equiv}/{len(cat_df)}"
                            )
                else:
                    print("  Equivalent (TOST): No tests performed")

            if split in self.contrast_results:
                contrast_df = self.contrast_results[split]
                sig_contrast = (
                    contrast_df["Significant"].value_counts().get("Yes", 0)
                )
                print(
                    "  Selective category differences: "
                    f"{sig_contrast}/{len(contrast_df)} comparisons"
                )