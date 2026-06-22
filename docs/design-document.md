# Design Document

# Design Document: PSALM 2.0 Courtroom-inspired Multi-Agent system for EU Copyright Infringement Evaluation

**Version**: 1.0
**Date**: June 16, 2026
**Authors**: Noah Scharrenberg
**Organization**: Maastricht University

## Introduction

### Purpose

This document outlines the design of a **courtroom-inspired multi-agent system (MAS)** for evaluating copyright infringement in the European Union (EU). The system focuses on assessing **character similarity, world-building similarity, and plot similarity** between a source text (copyright-protected) and a target text (potentially infringing) as an improvement to our prior framework **PSALM**. The goal is to provide a **modular, explainable, and accurate** framework that simulates courtroom dynamics to improve consistency and transparency in copyright infringement evaluations.

### Scope

* **Domain**: Copyright infringement evaluation in the EU.
* **Evaluation Dimensions**: Character similarity, world-building similarity, plot similarity.
* **Verdict System**: Three-category system (Guilty/Infringing, Not Guilty/Not Infringing, Undecided/Borderline).
* **Constraints**:
  * No external data or tool calling for evidence gathering (except for agent communication via MCP/A2A).
  * Self-contained: Operates using only provided text pairs and predefined dimensions.
  * Compliant with **EU AI Act, copyright regulations, and CDSM Directive**.

### Objective

1. **Accuracy**: Prioritize alignment with legal outcomes.
2. **Explainability**: Ensure transparency in reasoning through structured argumentation.
3. **Modularity**: Enable experimentation with agent roles, debate structures, and voting mechanisms.
4. **Compliance**: Embed legal and ethical constraints in agent prompts and system rules.

## Framework Overview

### Core Principles

* **Accuracy-First**: Prioritize alignment with legal outcomes, while ensuring explainability.
* **Modularity**: All components (agent roles, debate structures, voting mechanisms) are configurable and experimentable.
* **Compliance**: Embed EU AI Act, copyright regulations, and CDSM constraints in agent prompts and system rules.
* **Self-Contained**: Operate using only provided text pairs and predefined dimensions.
* **Explainability**: Provide step-by-step rationales and debate summaries for all verdicts.
* **Fallback**: Default to "Undecided" if deliberation fails.

### High-Level Architecture

Architecture diagram can be found in [docs/diagrams.md](https://github.com/nscharrenberg/psalm/blob/v2/docs/diagrams.md#high-level-architecture)

The MAS consists of the following core components:

1. **Agent Roles**: Judge, Prosecutor, Defense Attorney, Adjudicators (Jury).
2. **Interaction Protocols**: Shared message queue, MCP/A2A for agent communication.
3. **Debate Structure**: Multi-round debates with adaptive stability detection.
4. **Voting Mechanisms**: Simple majority → trust-weighted voting → Judge tie-breaker.
5. **Legal Framework**: Embedded rules for substantial similarity and filtering unprotectable elements.

## Agent Roles and Architecture

### Role Definitions

| **Role**                | **Responsibilities**                                                                                                                                                    | **Key Constraints**                                                                                           | **Modularity Considerations**                                                                           |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| **Judge**               | Moderates debate, enforces legal procedures, resolves disputes, clarifies ambiguities, and intervenes to dismiss low-quality or irrelevant arguments.                   | Operates using predefined rules embedded in prompts. Authority to dismiss arguments is configurable.          | Can experiment with enabling/disabling authority to dismiss arguments.                                  |
| **Prosecutor**          | Gathers evidence from text pairs, constructs arguments for infringement based on predefined dimensions (character, world-building, plot).                               | Uses structured templates (e.g., checklists, grading rubrics) and LLM-driven comparisons to propose evidence. | Can experiment with different evidence-gathering processes (e.g., agent per dimension or single agent). |
| **Defense Attorney**    | Gathers counter-evidence, constructs arguments against infringement, and engages in cross-examination **only when discrepancies or alternative interpretations exist**. | Focuses on challenging the Prosecutor’s evidence (e.g., discrepancies, alternative interpretations).          | Can experiment with different cross-examination strategies.                                             |
| **Adjudicators (Jury)** | Evaluates arguments, forms individual verdicts with reasoning, deliberates in multi-round debates if no consensus is reached.                                           | Votes using simple majority → trust-weighted voting → plurality with Judge tie-breaker.                       | Can experiment with different deliberation structures (e.g., debate-to-consensus, fixed rounds).        |

### Agent Interaction Protocols

* **Communication Flow**:
  * Agents interact via a **shared message queue** (default), where arguments, evidence, and counter-evidence are publicly posted.
  * **MCP and A2A protocols** are supported for agent communication (but not for external data or tool calling in the initial phase).
* **Debate Structure**:
  * **Default**: 5 rounds of debate, configurable or disableable.
  * **Time Limits**: **Default: 3 minutes per round per agent**, configurable or disableable.
  * **Adaptive Stability Detection**: Debate terminates early if consensus is reached.
* **Evidence and Argument Rules**:
  * Agents are **not tasked with finding new evidence** after the initial evidence-gathering phase.
  * The **Judge intervenes** if agents attempt to introduce new evidence or low-quality arguments.

## Legal Framework Integration

### Operationalizing "Substantial Similarity"

* **Dimensions**: Focus on **character similarity, world-building similarity, and plot similarity** (modular for future extension).
* **Unprotectable Elements**: Provided in agent instructions (e.g., "Do not consider generic tropes like 'a chosen one'"). These are **not removed in preprocessing** but are explicitly flagged for agents to ignore.
* **Operationalization Methods**:
  * **Predefined Checklists**: Agents use structured templates to compare specific elements (e.g., character traits, plot points).
  * **LLM-Driven Comparisons**: Agents use LLM capabilities to generate and structure arguments (e.g., "Compare the world-building of Source Text and Target Text").
  * **Grading Rubrics**: Agents may use rubrics to quantify similarities (e.g., "Character A and B share 3/5 unique traits").

### Handling Borderline Cases

* Borderline cases are **discussed through arguments and evidence** provided by the Prosecutor and Defense Attorney.
* Adjudicators may vote **"Undecided"** if the case is not clearly infringing or non-infringing.

## Evaluation and Validation

### Test Cases and Ground Truth

* **Test Cases**: **Synthetic**, designed to cover a range of scenarios (e.g., clear infringement, clear non-infringement, borderline cases).
* **Ground Truth**: Established via **human annotation** (e.g., legal experts or researchers).

### Metrics

* **Accuracy**: Alignment with ground truth verdicts.
* **Consistency**: Same input → same output across similar cases.
* **Explainability**: Clarity and coherence of agent rationales and debate summaries.
* **Robustness&#x20;**(optional): Performance under adversarial inputs (e.g., noisy or misleading texts).

### Validation Approach

* **Synthetic Benchmark**: Develop a benchmark to evaluate **accuracy** (against ground truth) and **consistency** (across similar cases).
* **Comparison**:
  * Compare against **PSALM** (with simplified 3-category verdict interpretation).
  * Compare against **simple prompting** (e.g., legal syllogism) as a baseline.

## Technical Implementation

### Agent Architecture

* **Default**: **Direct interaction** between agents (no Meta-LLM).
* **Modularity**: Support for experimenting with **Meta-LLM coordination** in future work.

### Agent Prompts

* **Judge**:
  * Includes **rules for debate moderation** (e.g., "Dismiss arguments that violate logical consistency").
  * Configurable authority to **intervene and dismiss low-quality arguments**.
* **Prosecutor/Defense**:
  * Includes **guidelines for evidence extraction** (e.g., "Focus on character traits, plot points, and world-building elements").
  * **Cross-examination**: Only performed when discrepancies or alternative interpretations exist.

### Deliberation and Voting Mechanisms

* **Voting Process**:
  1. Adjudicators **vote with reasoning**.
  2. If **unanimous**, verdict is finalized, and reasoning is synthesized.
  3. If **not unanimous**, multi-round debate occurs, with voting after each round until:
     * Unanimous consensus is reached.
     * \*\*Round limit\*\* is hit (default: 5 rounds).
  4. If round limit is hit:
     * \*\*Simple majority\*\* voting.
     * If tie, \*\*trust-weighted voting\*\* (e.g., based on agent trustworthiness or argument strength).
     * If still tied, \*\*plurality with Judge tie-breaker\*\*.
* **Adaptive Stability Detection**: Debate terminates early if no new arguments are introduced and consensus is unlikely to change.

### Explainability

* **Step-by-Step Rationales**: Each agent provides a **detailed rationale** for their arguments and votes.
* **Debate Summary**: Final verdict includes a **summary of key arguments** and how they influenced the decision.
* **Traceability**: All steps (arguments, counter-arguments, votes) are recorded and traceable in the final output.

## Modularity and Extensibility

| **Components**             | **Modularity Options**                                                     | **Default Setting**                       |
| -------------------------- | -------------------------------------------------------------------------- | ----------------------------------------- |
| **Agent Roles**            | Single agent per dimension vs. one agent handling all dimensions.          | One agent per role (Prosecutor, Defense). |
| **Evidence-Gathering**     | Structured templates, LLM-driven comparisons, checklists, grading rubrics. | LLM-driven + structured templates.        |
| **Cross-Examination**      | Only when discrepancies exist vs. mandatory cross-examination.             | Only when discrepancies exist.            |
| **Debate Structure**       | Fixed rounds vs. adaptive stability detection.                             | 5 rounds + adaptive stability.            |
| **Voting Mechanism**       | Simple majority → trust-weighted → Judge tie-breaker.                      | As described above.                       |
| **Communication Protocol** | Shared message queue vs. MCP/A2A.                                          | Shared message queue.                     |
| **Agent Architecture**     | Direct interaction vs. Meta-LLM coordination.                              | Direct interaction.                       |



## Challenges and Mitigations

| **Challenge**                | **Mitigation Strategy**                                                                           |
| ---------------------------- | ------------------------------------------------------------------------------------------------- |
| **Bias in Agent Arguments**  | Use diverse agent personas (e.g., "strict" vs. "lenient" adjudicators) and trust-weighted voting. |
| **Deadlock in Deliberation** | Implement adaptive stability detection and round limits to force a vote.                          |
| **Low-Quality Arguments**    | Judge intervenes to dismiss irrelevant or low-quality arguments.                                  |
| **Explainability Overhead**  | Limit rationale depth (e.g., "Provide a 3-sentence explanation for your vote").                   |
| **Scalability**              | Design agents to process texts in chunks if inputs are long.                                      |
| **Complete Failure**         | Default to "Undecided" if deliberation fails entirely.                                            |

## Future Extensions

The framework is designed to be **highly extensible** to accommodate a wide range of future enhancements. Below is a **comprehensive list of potential extensions**, organized by category:

### Strategy Experimentation

* **Voting Strategies**:
  * Experiment with alternative voting mechanisms (e.g., ranked-choice voting, Borda count, Condorcet methods).
  * Test dynamic weighting (e.g., weights based on agent performance history, confidence scores, or argument coherence).
* **Debating Structures**:
  * Turn-based vs. real-time asynchronous debates.
  * Hierarchical deliberation (e.g., sub-juries for sub-issues, reporting to a main jury).
  * Adversarial vs. collaborative debate styles.
* **Attorney Setups**:
  * Multiple prosecutors/defense attorneys (e.g., one per dimension or per argument type).
  * Specialized vs. generalist attorneys (e.g., one attorney handles all dimensions vs. dedicated attorneys per dimension).
* **Jury Setups**:
  * Homogeneous vs. heterogeneous juries (e.g., all LLM-based vs. mix of LLMs and human validators).
  * Dynamic jury composition (e.g., juries scaled based on case complexity).
  * Jury personalities (e.g., "strict," "lenient," or "balanced" adjudicators).

### Architecture Experimentation

* **Courtroom Setups**:
  * Direct interaction vs. Meta-LLM coordination (e.g., a central Meta-LLM assigns roles, moderates, and synthesizes outputs).
  * Hybrid architectures (e.g., some agents interact directly, while others are coordinated by a Meta-LLM).
  * Multi-layered systems (e.g., lower-level agents handle evidence gathering, while higher-level agents handle argumentation and deliberation).
* **Agent Orchestration**:
  * Dynamic role assignment (e.g., agents adapt roles based on case requirements).
  * Self-improving agents (e.g., agents refine their strategies based on feedback or past performance).

### External Knowledge Integration

* **Access to RAG or External Knowledge Bases**:
  * Use **MCP or similar protocols** to enable agents to:
    * Retrieve **similar cases** from legal databases (e.g., Casetext, LexisNexis).
    * Access **relevant laws, precedents, or legal tests** (e.g., EU copyright directives, case law).
  * Experiment with **hybrid reasoning** (e.g., combining internal agent deliberation with external legal knowledge).
* **Access to the Web**:
  * Enable agents to **search for similar cases or relevant laws** online (e.g., via web APIs or search engines).
  * Implement **fact-checking mechanisms** to validate claims using external sources.

### Autonomous Case Handling

* **Fully Autonomous Setup**:
  * **Dynamic Agent Generation**: When a case is provided, the system **automatically determines**:
    * What **agents are needed** (e.g., specialized prosecutors for specific dimensions like character or plot similarity).
    * What **prompts and roles** each agent should have (e.g., tailored instructions based on case details).
    * What **relevant laws or dimensions** apply (e.g., filtering for EU copyright law, identifying applicable legal tests).
  * **Scenario Simulation**: Like **Claude Code**, the system could:
    * **Spin up multiple agent teams** to explore different argumentation paths or scenarios.
    * **Simulate counterfactuals** (e.g., "What if the defense focused on fair use instead of lack of access?").
    * **Iteratively refine** arguments and strategies based on intermediate results.
  * **End-to-End Automation**:
    * From **case input** (e.g., source/target texts + jurisdiction) to **verdict output** with minimal human intervention.
    * **Self-configuration** of debate structures, voting mechanisms, and agent setups based on case complexity or domain.

# Appendix

## Glossary

| **Abbreviation** | **Term**                                         |
| ---------------- | ------------------------------------------------ |
| **MAS**          | Multi-Agent System                               |
| **MCP**          | Model Context Protocol                           |
| **A2A**          | Agent-to-Agent Protocol                          |
| **RAG**          | Retrieval-Augmented Generation                   |
| **CDSM**         | Copyright in the Digital Single Market Directive |
| **LLM**          | Large Language Model                             |

## Related Documents and Sources

The Design Document is based on the brainstormed methodology [Methodology](assets://./workspace/YVYQ-LuJUxL2vbnN930lC/LKem7lnZOGFFPFk9O5NwM) and performed literature study [Literature Study](assets://./workspace/YVYQ-LuJUxL2vbnN930lC/4DN-SQONOR6JL44Oc-FWH).
