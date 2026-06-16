import unsloth
from psalm.configs.experiments import ExtractionExperimentConfig
from psalm.experiments.extraction_experiment import ExtractionExperiment


def main():
    experiment = ExtractionExperiment(ExtractionExperimentConfig())
    experiment.execute()


if __name__ == "__main__":
    main()