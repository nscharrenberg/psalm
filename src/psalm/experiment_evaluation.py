from psalm.configs.experiments import EvaluationExperimentConfig
from psalm.experiments.evaluation_experiment import EvaluationExperiment


def main():
    experiment = EvaluationExperiment(EvaluationExperimentConfig())
    experiment.execute()


if __name__ == "__main__":
    main()