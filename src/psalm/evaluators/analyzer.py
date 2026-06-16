"""
Comprehensive Unlearning Analysis Script
Analyzes forget vs retain performance across memorization and stylometry metrics
"""
from pathlib import Path
from typing import Union

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from scipy.stats import mannwhitneyu, ttest_ind
import warnings

warnings.filterwarnings('ignore')

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


class UnlearningAnalyzer:
    def __init__(self, file_path: Union[str, Path]):
        """Initialize analyzer with CSV data"""

        if not isinstance(file_path, Path):
            file_path = Path(file_path)

        if file_path.suffix == '.csv':
            self.df = pd.read_csv(file_path)
        elif file_path.suffix == '.parquet':
            self.df = pd.read_parquet(file_path)
        else:
            raise NotImplementedError

        self._prepare_data()

    def _prepare_data(self):
        """Extract and organize metric scores"""
        # Define metric categories
        self.memorization_metrics = ['Exact Match_score', 'BLEU_score', 'ROUGE_score']
        self.stylometry_metrics = ['Writing Style_score', 'Narrative Voice_score']
        self.content_metrics = [
            'Character Similarity_score',
            'Plot Structure Similarity_score',
            'Scene Sequence Similarity_score',
            'WorldBuilding Similarity_score'
        ]
        self.copyright_metrics = [
            'Parody/Satire_score',
            'Pastiche_score',
            'Quotation/Citation_score',
            'Scènes à Faire_score'
        ]

        self.all_metrics = (self.memorization_metrics + self.stylometry_metrics +
                            self.content_metrics + self.copyright_metrics)

        # Split into forget and retain sets
        self.forget_df = self.df[self.df['is_forget'] == True].copy()
        self.retain_df = self.df[self.df['is_forget'] == False].copy()

        print(f"Dataset loaded:")
        print(f"  Forget samples: {len(self.forget_df)}")
        print(f"  Retain samples: {len(self.retain_df)}")
        print(f"  Total metrics: {len(self.all_metrics)}")

    def calculate_statistics(self):
        """Calculate comprehensive statistics for forget vs retain"""
        results = []

        for metric in self.all_metrics:
            forget_scores = self.forget_df[metric].dropna()
            retain_scores = self.retain_df[metric].dropna()

            if len(forget_scores) == 0 or len(retain_scores) == 0:
                continue

            # Descriptive statistics
            forget_mean = forget_scores.mean()
            forget_std = forget_scores.std()
            retain_mean = retain_scores.mean()
            retain_std = retain_scores.std()

            # Effect size (Cohen's d)
            pooled_std = np.sqrt(((len(forget_scores) - 1) * forget_std ** 2 +
                                  (len(retain_scores) - 1) * retain_std ** 2) /
                                 (len(forget_scores) + len(retain_scores) - 2))
            cohens_d = (forget_mean - retain_mean) / pooled_std if pooled_std > 0 else 0

            # Statistical tests
            # Mann-Whitney U (non-parametric)
            u_stat, p_value_mw = mannwhitneyu(forget_scores, retain_scores, alternative='two-sided')

            # T-test (parametric)
            t_stat, p_value_t = ttest_ind(forget_scores, retain_scores)

            results.append({
                'Metric': metric.replace('_score', ''),
                'Forget Mean': forget_mean,
                'Forget Std': forget_std,
                'Retain Mean': retain_mean,
                'Retain Std': retain_std,
                'Difference': forget_mean - retain_mean,
                "Cohen's d": cohens_d,
                'Mann-Whitney p': p_value_mw,
                'T-test p': p_value_t,
                'Significant (p<0.05)': 'Yes' if p_value_mw < 0.05 else 'No'
            })

        self.stats_df = pd.DataFrame(results)
        return self.stats_df

    def detect_outliers(self, method='iqr', threshold=1.5):
        """Detect outliers in forget set using IQR or Z-score method"""
        outliers = []

        for metric in self.all_metrics:
            forget_scores = self.forget_df[metric].dropna()

            if len(forget_scores) == 0:
                continue

            if method == 'iqr':
                Q1 = forget_scores.quantile(0.25)
                Q3 = forget_scores.quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - threshold * IQR
                upper_bound = Q3 + threshold * IQR

                outlier_mask = (self.forget_df[metric] < lower_bound) | (self.forget_df[metric] > upper_bound)

            elif method == 'zscore':
                z_scores = np.abs(stats.zscore(forget_scores))
                outlier_indices = forget_scores.index[z_scores > threshold]
                outlier_mask = self.forget_df.index.isin(outlier_indices)

            # Get outlier rows
            outlier_rows = self.forget_df[outlier_mask]

            for idx, row in outlier_rows.iterrows():
                outliers.append({
                    'test_id': row['ti_id'],
                    'author': row['author'],
                    'metric': metric.replace('_score', ''),
                    'score': row[metric],
                    'mean': forget_scores.mean(),
                    'std': forget_scores.std(),
                    'z_score': (row[
                                    metric] - forget_scores.mean()) / forget_scores.std() if forget_scores.std() > 0 else 0,
                    'reason': row[metric.replace('_score', '_reason')],
                    'question': row['question'][:100] + '...' if len(str(row['question'])) > 100 else row['question'],
                    'expected_answer': row['expected_answer'],
                    'actual_answer': row['actual_answer'],
                    'is_forget': row['is_forget'],
                })

        self.outliers_df = pd.DataFrame(outliers)
        return self.outliers_df

    def plot_comparison_boxplots(self, figsize=(20, 12)):
        """Create box plots comparing forget vs retain for all metrics"""
        n_metrics = len(self.all_metrics)
        n_cols = 4
        n_rows = int(np.ceil(n_metrics / n_cols))

        fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
        axes = axes.flatten()

        for idx, metric in enumerate(self.all_metrics):
            ax = axes[idx]

            data_to_plot = []
            labels = []

            forget_scores = self.forget_df[metric].dropna()
            retain_scores = self.retain_df[metric].dropna()

            if len(forget_scores) > 0:
                data_to_plot.append(forget_scores)
                labels.append('Forget')

            if len(retain_scores) > 0:
                data_to_plot.append(retain_scores)
                labels.append('Retain')

            bp = ax.boxplot(data_to_plot, labels=labels, patch_artist=True)

            # Color boxes
            colors = ['#ff6b6b', '#4ecdc4']
            for patch, color in zip(bp['boxes'], colors[:len(bp['boxes'])]):
                patch.set_facecolor(color)
                patch.set_alpha(0.6)

            # Add mean markers
            for i, data in enumerate(data_to_plot):
                ax.scatter(i + 1, data.mean(), color='red', s=100, zorder=3, marker='D', label='Mean' if i == 0 else '')

            ax.set_title(metric.replace('_score', ''), fontsize=10, fontweight='bold')
            ax.set_ylabel('Score', fontsize=9)
            ax.grid(True, alpha=0.3)

            # Add statistical annotation
            if len(data_to_plot) == 2:
                _, p_value = mannwhitneyu(data_to_plot[0], data_to_plot[1])
                sig_text = '***' if p_value < 0.001 else '**' if p_value < 0.01 else '*' if p_value < 0.05 else 'ns'
                ax.text(0.5, 0.95, f'p={p_value:.4f} ({sig_text})',
                        transform=ax.transAxes, ha='center', va='top', fontsize=8,
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        # Hide empty subplots
        for idx in range(n_metrics, len(axes)):
            axes[idx].axis('off')

        plt.tight_layout()
        plt.savefig('comparison_boxplots.png', dpi=300, bbox_inches='tight')
        print("✓ Saved comparison_boxplots.png")
        return fig

    def plot_metric_heatmap(self, figsize=(16, 10)):
        """Create heatmap showing all scores"""
        # Prepare data for heatmap
        forget_means = self.forget_df[self.all_metrics].mean()
        retain_means = self.retain_df[self.all_metrics].mean()

        data = pd.DataFrame({
            'Forget': forget_means,
            'Retain': retain_means
        })

        data.index = [m.replace('_score', '') for m in data.index]

        fig, ax = plt.subplots(figsize=figsize)
        sns.heatmap(data.T, annot=True, fmt='.3f', cmap='RdYlGn',
                    center=0.5, vmin=0, vmax=1, cbar_kws={'label': 'Score'},
                    linewidths=0.5, ax=ax)

        ax.set_title('Mean Scores Heatmap: Forget vs Retain', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('')
        ax.set_ylabel('')

        plt.tight_layout()
        plt.savefig('metric_heatmap.png', dpi=300, bbox_inches='tight')
        print("✓ Saved metric_heatmap.png")
        return fig

    def plot_category_comparison(self, figsize=(14, 10)):
        """Plot comparison by metric category"""
        categories = {
            'Memorization': self.memorization_metrics,
            'Stylometry': self.stylometry_metrics,
            'Content': self.content_metrics,
            'Copyright': self.copyright_metrics
        }

        fig, axes = plt.subplots(2, 2, figsize=figsize)
        axes = axes.flatten()

        for idx, (cat_name, metrics) in enumerate(categories.items()):
            ax = axes[idx]

            forget_means = []
            retain_means = []
            metric_names = []

            for metric in metrics:
                if metric in self.df.columns:
                    forget_means.append(self.forget_df[metric].mean())
                    retain_means.append(self.retain_df[metric].mean())
                    metric_names.append(metric.replace('_score', '').replace(' Similarity', ''))

            x = np.arange(len(metric_names))
            width = 0.35

            bars1 = ax.bar(x - width / 2, forget_means, width, label='Forget', color='#ff6b6b', alpha=0.7)
            bars2 = ax.bar(x + width / 2, retain_means, width, label='Retain', color='#4ecdc4', alpha=0.7)

            # Add value labels
            for bars in [bars1, bars2]:
                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width() / 2., height,
                            f'{height:.2f}',
                            ha='center', va='bottom', fontsize=8)

            ax.set_ylabel('Mean Score', fontsize=11)
            ax.set_title(f'{cat_name} Metrics', fontsize=13, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(metric_names, rotation=45, ha='right', fontsize=9)
            ax.legend()
            ax.grid(True, alpha=0.3, axis='y')
            ax.set_ylim(0, 1.1)

        plt.tight_layout()
        plt.savefig('category_comparison.png', dpi=300, bbox_inches='tight')
        print("✓ Saved category_comparison.png")
        return fig

    def plot_violin_distributions(self, figsize=(20, 10)):
        """Create violin plots for key metrics"""
        key_metrics = self.memorization_metrics + self.stylometry_metrics

        fig, axes = plt.subplots(2, 3, figsize=figsize)
        axes = axes.flatten()

        for idx, metric in enumerate(key_metrics):
            if idx >= len(axes):
                break

            ax = axes[idx]

            # Prepare data
            forget_data = self.forget_df[[metric, 'is_forget']].copy()
            forget_data['Set'] = 'Forget'

            retain_data = self.retain_df[[metric, 'is_forget']].copy()
            retain_data['Set'] = 'Retain'

            combined = pd.concat([
                forget_data[[metric, 'Set']],
                retain_data[[metric, 'Set']]
            ])

            # Violin plot
            parts = ax.violinplot(
                [forget_data[metric].dropna(), retain_data[metric].dropna()],
                positions=[1, 2],
                showmeans=True,
                showmedians=True
            )

            # Color violins
            colors = ['#ff6b6b', '#4ecdc4']
            for pc, color in zip(parts['bodies'], colors):
                pc.set_facecolor(color)
                pc.set_alpha(0.6)

            ax.set_xticks([1, 2])
            ax.set_xticklabels(['Forget', 'Retain'])
            ax.set_ylabel('Score', fontsize=10)
            ax.set_title(metric.replace('_score', ''), fontsize=11, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')

        # Hide empty subplot if odd number of metrics
        if len(key_metrics) < len(axes):
            axes[-1].axis('off')

        plt.tight_layout()
        plt.savefig('violin_distributions.png', dpi=300, bbox_inches='tight')
        print("✓ Saved violin_distributions.png")
        return fig

    def plot_correlation_matrix(self, figsize=(14, 12)):
        """Plot correlation matrix for forget set"""
        forget_scores = self.forget_df[self.all_metrics].dropna()

        corr = forget_scores.corr()

        # Clean labels
        corr.index = [m.replace('_score', '') for m in corr.index]
        corr.columns = [m.replace('_score', '') for m in corr.columns]

        fig, ax = plt.subplots(figsize=figsize)
        sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm',
                    center=0, vmin=-1, vmax=1,
                    square=True, linewidths=0.5, ax=ax,
                    cbar_kws={'label': 'Correlation'})

        ax.set_title('Correlation Matrix (Forget Set)', fontsize=16, fontweight='bold', pad=20)
        plt.tight_layout()
        plt.savefig('correlation_matrix.png', dpi=300, bbox_inches='tight')
        print("✓ Saved correlation_matrix.png")
        return fig

    def plot_outlier_analysis(self, figsize=(16, 10)):
        """Visualize outliers"""
        if len(self.outliers_df) == 0:
            print("No outliers detected.")
            return None

        fig, axes = plt.subplots(2, 2, figsize=figsize)

        # 1. Outliers by metric
        ax1 = axes[0, 0]
        outlier_counts = self.outliers_df['metric'].value_counts()
        outlier_counts.plot(kind='barh', ax=ax1, color='#e74c3c')
        ax1.set_title('Number of Outliers by Metric', fontsize=12, fontweight='bold')
        ax1.set_xlabel('Count')
        ax1.grid(True, alpha=0.3, axis='x')

        # 2. Outliers by author
        ax2 = axes[0, 1]
        author_counts = self.outliers_df['author'].value_counts().head(10)
        author_counts.plot(kind='barh', ax=ax2, color='#9b59b6')
        ax2.set_title('Top 10 Authors with Outliers', fontsize=12, fontweight='bold')
        ax2.set_xlabel('Count')
        ax2.grid(True, alpha=0.3, axis='x')

        # 3. Z-score distribution
        ax3 = axes[1, 0]
        self.outliers_df['z_score'].hist(bins=30, ax=ax3, color='#3498db', alpha=0.7, edgecolor='black')
        ax3.axvline(3, color='red', linestyle='--', label='±3σ threshold')
        ax3.axvline(-3, color='red', linestyle='--')
        ax3.set_title('Distribution of Outlier Z-scores', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Z-score')
        ax3.set_ylabel('Frequency')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # 4. Score vs Mean scatter
        ax4 = axes[1, 1]
        ax4.scatter(self.outliers_df['mean'], self.outliers_df['score'],
                    c=self.outliers_df['z_score'], cmap='RdYlGn_r',
                    s=100, alpha=0.6, edgecolors='black')
        ax4.plot([0, 1], [0, 1], 'k--', alpha=0.3, label='y=x')
        ax4.set_title('Outlier Scores vs Category Mean', fontsize=12, fontweight='bold')
        ax4.set_xlabel('Category Mean Score')
        ax4.set_ylabel('Outlier Score')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        cbar = plt.colorbar(ax4.collections[0], ax=ax4)
        cbar.set_label('Z-score')

        plt.tight_layout()
        plt.savefig('outlier_analysis.png', dpi=300, bbox_inches='tight')
        print("✓ Saved outlier_analysis.png")
        return fig

    def plot_author_comparison(self, top_n=10, figsize=(16, 10)):
        """Compare performance across authors"""
        # Get top authors by sample count in forget set
        top_authors = self.forget_df['author'].value_counts().head(top_n).index

        fig, axes = plt.subplots(2, 2, figsize=figsize)

        categories = {
            'Memorization': self.memorization_metrics,
            'Stylometry': self.stylometry_metrics
        }

        for idx, (cat_name, metrics) in enumerate(categories.items()):
            # Forget set
            ax_forget = axes[idx, 0]
            # Retain set
            ax_retain = axes[idx, 1]

            forget_means_by_author = []
            retain_means_by_author = []

            for author in top_authors:
                author_forget = self.forget_df[self.forget_df['author'] == author]
                author_retain = self.retain_df[self.retain_df['author'] == author]

                forget_mean = author_forget[metrics].mean().mean()
                retain_mean = author_retain[metrics].mean().mean()

                forget_means_by_author.append(forget_mean)
                retain_means_by_author.append(retain_mean)

            # Plot forget
            ax_forget.barh(range(len(top_authors)), forget_means_by_author, color='#ff6b6b', alpha=0.7)
            ax_forget.set_yticks(range(len(top_authors)))
            ax_forget.set_yticklabels(top_authors, fontsize=9)
            ax_forget.set_xlabel('Mean Score', fontsize=10)
            ax_forget.set_title(f'{cat_name} - Forget Set', fontsize=11, fontweight='bold')
            ax_forget.grid(True, alpha=0.3, axis='x')
            ax_forget.set_xlim(0, 1)

            # Plot retain
            ax_retain.barh(range(len(top_authors)), retain_means_by_author, color='#4ecdc4', alpha=0.7)
            ax_retain.set_yticks(range(len(top_authors)))
            ax_retain.set_yticklabels(top_authors, fontsize=9)
            ax_retain.set_xlabel('Mean Score', fontsize=10)
            ax_retain.set_title(f'{cat_name} - Retain Set', fontsize=11, fontweight='bold')
            ax_retain.grid(True, alpha=0.3, axis='x')
            ax_retain.set_xlim(0, 1)

        plt.tight_layout()
        plt.savefig('author_comparison.png', dpi=300, bbox_inches='tight')
        print("✓ Saved author_comparison.png")
        return fig

    def generate_summary_report(self):
        """Generate text summary of key findings"""
        report = []
        report.append("=" * 80)
        report.append("UNLEARNING ANALYSIS SUMMARY REPORT")
        report.append("=" * 80)
        report.append("")

        # Dataset overview
        report.append("DATASET OVERVIEW:")
        report.append(f"  Total samples: {len(self.df)}")
        report.append(f"  Forget samples: {len(self.forget_df)}")
        report.append(f"  Retain samples: {len(self.retain_df)}")
        report.append(f"  Unique authors: {self.df['author'].nunique()}")
        report.append("")

        # Memorization metrics
        report.append("MEMORIZATION REMOVAL (Lower is better for Forget):")
        report.append("-" * 80)
        for metric in self.memorization_metrics:
            forget_mean = self.forget_df[metric].mean()
            retain_mean = self.retain_df[metric].mean()
            difference = forget_mean - retain_mean

            stat_row = self.stats_df[self.stats_df['Metric'] == metric.replace('_score', '')]
            if len(stat_row) > 0:
                p_value = stat_row.iloc[0]['Mann-Whitney p']
                cohens_d = stat_row.iloc[0]["Cohen's d"]
                sig = "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else "ns"

                report.append(f"  {metric.replace('_score', '')}:")
                report.append(f"    Forget: {forget_mean:.4f} | Retain: {retain_mean:.4f} | Δ: {difference:.4f}")
                report.append(f"    p-value: {p_value:.6f} ({sig}) | Cohen's d: {cohens_d:.3f}")

                # Interpret Cohen's d
                if abs(cohens_d) < 0.2:
                    effect = "negligible"
                elif abs(cohens_d) < 0.5:
                    effect = "small"
                elif abs(cohens_d) < 0.8:
                    effect = "medium"
                else:
                    effect = "large"
                report.append(f"    Effect size: {effect}")
                report.append("")

        # Stylometry metrics
        report.append("STYLOMETRY REMOVAL (Lower is better for Forget):")
        report.append("-" * 80)
        for metric in self.stylometry_metrics:
            forget_mean = self.forget_df[metric].mean()
            retain_mean = self.retain_df[metric].mean()
            difference = forget_mean - retain_mean

            stat_row = self.stats_df[self.stats_df['Metric'] == metric.replace('_score', '')]
            if len(stat_row) > 0:
                p_value = stat_row.iloc[0]['Mann-Whitney p']
                cohens_d = stat_row.iloc[0]["Cohen's d"]
                sig = "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else "ns"

                report.append(f"  {metric.replace('_score', '')}:")
                report.append(f"    Forget: {forget_mean:.4f} | Retain: {retain_mean:.4f} | Δ: {difference:.4f}")
                report.append(f"    p-value: {p_value:.6f} ({sig}) | Cohen's d: {cohens_d:.3f}")

                if abs(cohens_d) < 0.2:
                    effect = "negligible"
                elif abs(cohens_d) < 0.5:
                    effect = "small"
                elif abs(cohens_d) < 0.8:
                    effect = "medium"
                else:
                    effect = "large"
                report.append(f"    Effect size: {effect}")
                report.append("")

        # Overall effectiveness
        report.append("OVERALL UNLEARNING EFFECTIVENESS:")
        report.append("-" * 80)

        # Calculate average scores
        forget_mem_avg = self.forget_df[self.memorization_metrics].mean().mean()
        retain_mem_avg = self.retain_df[self.memorization_metrics].mean().mean()
        forget_style_avg = self.forget_df[self.stylometry_metrics].mean().mean()
        retain_style_avg = self.retain_df[self.stylometry_metrics].mean().mean()

        mem_reduction = ((retain_mem_avg - forget_mem_avg) / retain_mem_avg * 100) if retain_mem_avg > 0 else 0
        style_reduction = (
                    (retain_style_avg - forget_style_avg) / retain_style_avg * 100) if retain_style_avg > 0 else 0

        report.append(f"  Memorization reduction: {mem_reduction:.2f}%")
        report.append(f"    Forget avg: {forget_mem_avg:.4f} | Retain avg: {retain_mem_avg:.4f}")
        report.append(f"  Stylometry reduction: {style_reduction:.2f}%")
        report.append(f"    Forget avg: {forget_style_avg:.4f} | Retain avg: {retain_style_avg:.4f}")
        report.append("")

        # Outliers
        if len(self.outliers_df) > 0:
            report.append("OUTLIERS DETECTED:")
            report.append("-" * 80)
            report.append(f"  Total outliers: {len(self.outliers_df)}")
            report.append(f"  Metrics with most outliers:")
            top_outlier_metrics = self.outliers_df['metric'].value_counts().head(5)
            for metric, count in top_outlier_metrics.items():
                report.append(f"    {metric}: {count}")
            report.append("")

            # Most extreme outliers
            report.append("  Most extreme outliers (by Z-score):")
            extreme = self.outliers_df.nlargest(5, 'z_score')[
                ['test_id', 'author', 'metric', 'score', 'z_score']
            ]
            for _, row in extreme.iterrows():
                report.append(f"    {row['test_id']} | {row['author']} | {row['metric']}")
                report.append(f"      Score: {row['score']:.4f} | Z-score: {row['z_score']:.2f}")
            report.append("")

        report.append("=" * 80)

        # Print and save
        report_text = "\n".join(report)
        print(report_text)

        with open('analysis_summary.txt', 'w', encoding='utf-8') as f:
            f.write(report_text)
        print("\n✓ Saved analysis_summary.txt")

        return report_text

    def export_detailed_results(self):
        """Export detailed analysis to Excel"""
        with pd.ExcelWriter('detailed_analysis.xlsx', engine='openpyxl') as writer:
            # Statistics summary
            self.stats_df.to_excel(writer, sheet_name='Statistics', index=False)

            # Outliers
            if len(self.outliers_df) > 0:
                self.outliers_df.to_excel(writer, sheet_name='Outliers', index=False)

            # Per-author summary
            author_summary = []
            for author in self.df['author'].unique():
                author_forget = self.forget_df[self.forget_df['author'] == author]
                author_retain = self.retain_df[self.retain_df['author'] == author]

                if len(author_forget) > 0:
                    author_summary.append({
                        'Author': author,
                        'Forget_Count': len(author_forget),
                        'Retain_Count': len(author_retain),
                        'Forget_Mem_Avg': author_forget[self.memorization_metrics].mean().mean(),
                        'Forget_Style_Avg': author_forget[self.stylometry_metrics].mean().mean(),
                        'Retain_Mem_Avg': author_retain[self.memorization_metrics].mean().mean() if len(
                            author_retain) > 0 else None,
                        'Retain_Style_Avg': author_retain[self.stylometry_metrics].mean().mean() if len(
                            author_retain) > 0 else None,
                    })

            pd.DataFrame(author_summary).to_excel(writer, sheet_name='Author_Summary', index=False)

            # Raw scores
            score_cols = ['ti_id', 'author', 'is_forget'] + self.all_metrics
            self.df[score_cols].to_excel(writer, sheet_name='Raw_Scores', index=False)

        print("✓ Saved detailed_analysis.xlsx")

    def run_full_analysis(self):
        """Run complete analysis pipeline"""
        print("\n" + "=" * 80)
        print("STARTING COMPREHENSIVE UNLEARNING ANALYSIS")
        print("=" * 80 + "\n")

        # 1. Calculate statistics
        print("1. Calculating statistics...")
        self.calculate_statistics()
        print(f"   ✓ Statistics calculated for {len(self.stats_df)} metrics\n")

        # 2. Detect outliers
        print("2. Detecting outliers...")
        self.detect_outliers(method='iqr', threshold=1.5)
        print(f"   ✓ Found {len(self.outliers_df)} outliers\n")

        # 3. Generate visualizations
        print("3. Generating visualizations...")
        self.plot_comparison_boxplots()
        self.plot_metric_heatmap()
        self.plot_category_comparison()
        self.plot_violin_distributions()
        self.plot_correlation_matrix()
        if len(self.outliers_df) > 0:
            self.plot_outlier_analysis()
        self.plot_author_comparison()
        print("")

        # 4. Generate reports
        print("4. Generating summary report...")
        self.generate_summary_report()
        print("")

        # 5. Export detailed results
        print("5. Exporting detailed results...")
        self.export_detailed_results()
        print("")

        print("=" * 80)
        print("ANALYSIS COMPLETE!")
        print("=" * 80)
        print("\nGenerated files:")
        print("  📊 comparison_boxplots.png")
        print("  📊 metric_heatmap.png")
        print("  📊 category_comparison.png")
        print("  📊 violin_distributions.png")
        print("  📊 correlation_matrix.png")
        if len(self.outliers_df) > 0:
            print("  📊 outlier_analysis.png")
        print("  📊 author_comparison.png")
        print("  📄 analysis_summary.txt")
        print("  📑 detailed_analysis.xlsx")