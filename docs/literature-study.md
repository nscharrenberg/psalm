# Literature Study

# Aim of this literature study

* Get insights from existing MAS frameworks, courtroom-inspired systems, argumentation and explainability techniques, and EU copyright law to inform the design of a specialized MAS for evaluating copyright infringement.
* Focus on structuring agent roles, evidence gathering, argumentation, deliberation, and verdict derivation, with particular attention to handling character, world-building and plot similarity.
* Explore how jury deliberation and voting mechanisms can be modeled within MAS to support consensus-building and verdict consistency.

# Multi-Agent Systems

* model complex legal reasoning processes.
* Distributing tasks among specialized agents.
* Simulate courtroom dynamics (gather and debate evidence, and derive verdicts through collaborative deliberation).
* Gap: While MAS frameworks exist for general legal reasoning and courtroom simulation, none seem to specifically be tailored to copyright infringement evaluation in the EU context.

# Related Work

## Multi-Agent Systems in Legal Contexts

* Generally employs hierarchical architecture with a Meta-LLM coordinating multiple sub-agents \[7, 11].
  * Meta-LLM decomposes complex legal tasks into subtasks assigned to specialized agents, ensuring efficient task distribution and coherent outputs\[1, 7].
  * Such architecture supports modularity, collaboration, and conflict resolution through mediation-based models.
* Communication protocols (model context protocol and agent-to-agent) standardize agent interactions, enabling scalable, auditable, and policy-compliant communication.
  * Facilitate access to external tools and contextual data, as well as, peer coordination and delegation, which are essential for legal reasoning where evidence and arguments must be systematically exchanged and evaluated.
* Frameworks like J1-EVAL and LegalSim simulate courtroom interactions and legal system dynamics \[9, 10, 11].
  * They model multi-role collaborative evaluation systems and provide structured approaches to analyze agent interactions within legal frameworks.
  * The simulations help capture the complexity of legal deliberation and decision-making process.

## Argumentation and Deliberation Frameworks

* Argumentation is a foundation of legal reasoning and explainability in AI systems \[12].
  * Computational models of argumentation capture the defeasible, contestable, and value-sensitive nature of law, providing a robust foundation for explainable legal AI.
  * This is crucial in legal contexts where opacity undermines trust and fairness.
  * Techniques such as the "who said what" relation map agents to their arguments, enabling assessment of argument strength and agent trustworthiness.
* Regulatory alignment with frameworks like the EU's GDPR and AI Act is essential to ensure compliance with ethical and legal standards \[12].
  * Alignment enhances transparency and trustworthiness, addressing challenges such as bias mitigation and empirical validation in judicial settings.
* Adaptive stability detection and structured argumentation frameworks improve the robustness of multi-agent debates \[13].
  * Thes techniques help manage debate rounds, voting mechanisms, and consensus-building, which are crucial for handling non-unanimous decisions and ensuring verdict consistency.

## Copyright Infringement and Similarity Assessment in the EU using MAS

* No existing MAS frameworks seem to directly address copyright infringement evaluation.

## Jury Deliberation and Voting Mechanisms

* Jury deliberation in MAS is modeled through multi-round debates and voting mechanisms \[1, 5].
  * Frameworks like AgentsBench and AgentCourt simulate courtroom dynamics with multiple agents representing different legal roles, engaging in adversarial debate and collaborative deliberation to reach consensus or verdicts.
* Strategies to handle non-unanimous decisions include debate rounds, voting mechanisms, and consensus-building techniques \[13].
  * These approaches ensure that dissenting opinions are systemtically addressed and that final decisions reflect a collective judgement, which is critical for legal contexts where multiple viewpoints must be reconciled.

# Comparative Table

| **Framework**          | **Roles Defined**                                                 | **Deliberation Method**            | **Verdict Mechanism**               | **Domain**                | **Relevant Features for Our Research**                     |
| ---------------------- | ----------------------------------------------------------------- | ---------------------------------- | ----------------------------------- | ------------------------- | ---------------------------------------------------------- |
| **AgentsBench \[1]**   | Judge & Jurors                                                    | Multi-round debate, voting         | Consensus-based final decision      | Legal judgment prediction | Structured deliberation, role specialization, voting       |
| **SAMVAD \[2]**        | Judge, Prosecution Counsel, Defense Counsel, Adjudicators (jury)  | Simulated judicial interactions    | Legal reasoning and decision-making | Indian legal context      | Multi-agent simulation, legal grounding                    |
| **L-MARS \[3]**        | Query Agent, Search Agent, Judge Agent, Summary Agent             | Task decomposition, feedback loops | Coherent outputs via Meta-LLM       | General legal reasoning   | Modularity, collaboration, conflict resolution             |
| **CAMEL \[4]**         | Not specified                                                     | Not specified                      | Not specified                       | General legal tasks       | Focus on legal reasoning and argumentation                 |
| **AgentsCourt \[5]**   | Judge, Plaintiff/prosecutor, Defendant.                           | Adversarial debate, mediation      | Judgment generation                 | Courtroom simulation      | Adversarial evolution, role-specific agents, debate rounds |
| **Courtroom-LLM \[6]** | Prosecution, Defense, Judge                                       | Debate, questioning, mediation     | Dynamic decision-making loop        | Legal case evaluation     | Mediation, multi-round debate, role mimicry                |
| **MASLegalBench \[7]** | Multiple legal agents                                             | Deduction, legal reasoning         | Legal conclusion                    | Legal reasoning benchmark | Benchmarking, legal knowledge integration                  |

# Insights & Gaps

* Existing MAS frameworks provide a strong foundation for modeling legal reasoning and courtroom dynamics, but do not specifically address copyright infringement evaluation in the EU context.
  * The courtroom-inspired framework emphasize distinct agent roles, structured argumentation, and deliberation processes that can be directly adapted to the proposed MAS design.
* Argumentation-based explainability and adaptive stability detection techniques offer methodologies to enhance the robustness and transparency of the MAS deliberation process.
  * These techniques align with EU regulatory frameworks and can help address challenges such as bias mitigation and empirical validation.
* Jury deliberation and voting mechanisms in MAS offer models for handling consensus-building and dissent, which are directly applicable to our idea of a simplified three-category verdict system (Infringing, Not Infringing, Undecided).
  * The MAs can incorporate these mechanisms to ensure verdict consistency and reliability.



# Some Methodological Considerations

* **Agent Roles and Architecture:** the MAS should include distinct roles such as judge, prosecutor, defense attorney, and adjudicators (jury), each driven by LLMs specialized for their respective tasks.
  * The Meta-LLM should coordinate task decomposition and feedback integration to ensure coherent outputs.
* **Communication Protocols**: Implementing MCP and A2A protocols will facilitate structured, interoperable, and policy-compliance communication among agents, enabling efficient evidence gathering and argument exchange.
* **Argumentation and Explainability**: Incorporating computational argumentation frameworks with "who said what" relations will enhance explainability and trustworthiness, aligning with EU regulatory standards. Adaptive stability detection can improve debate robustness.
* **Legal Framework Integration**: The MAS must embed the EU copyright legal framework, focusing on filtering unprotectable elements and evaluating the "total concept and feel" of works to determine substantial similarity across character, world-building and plot dimensions.
* **Jury Deliberation and Voting**: Modeling jury deliberation through multi-round debates and voting mechanisms will support consensus-building and handle dissent, ensuring verdict consistency and reliability.

# References

* \[1] [AgentsBench: A Multi-Agent LLM Simulation Framework for Legal Judgment Prediction](https://www.mdpi.com/2079-8954/13/8/641)
* \[2] [SAMVAD: A Multi-Agent System for Simulating Judicial Deliberation Dynamics in India](https://arxiv.org/abs/2509.03793)
* \[3] [L-MARS: Legal Multi-Agent Workflow with Orchestrated Reasoning and Agentic Search](https://arxiv.org/abs/2509.00761)
* \[4] [CAMEL: Communicative Agents for "Mind" Exploration of Large Language Model Society](https://arxiv.org/abs/2303.17760)
* \[5] [AgentsCourt: Building Judicial Decision-Making Agents with Court Debate Simulation and Legal Knowledge Augmentation](https://aclanthology.org/2024.findings-emnlp.549/)
* \[6] [Courtroom-LLM: A Legal-Inspired Multi-LLM Framework for Resolving Ambiguous Text Classifications](https://aclanthology.org/2025.coling-main.493/)
* \[7] [MASLegalBench: Benchmarking Multi-Agent Systems in Deductive Legal Reasoning](https://arxiv.org/abs/2509.24922)
* \[8] [AgentDevLaw: A Middleware Architecture for Integrating Legal Ontologies and Multi-agent Systems](https://link.springer.com/chapter/10.1007/978-3-030-61380-8_3) (page 33 - 46)
* \[9] [Ready Jurist One: Benchmarking Language Agents for Legal Intelligence in Dynamic Environments](https://arxiv.org/abs/2507.04037)
* \[10] [LegalSim: Multi-Agent Simulation of Legal Systems for Discovering Procedural Exploits](https://arxiv.org/abs/2510.03405)
* \[11] [From single-agent to multi-agent: a comprehensive review of LLM-based legal agents](https://www.oaepublish.com/articles/aiagent.2025.06)
* \[12] [Argumentation-Based Explainability for Legal AI: Comparative and Regulatory Perspectives](https://arxiv.org/abs/2510.11079)
* \[13] [Multi-Agent Debate for LLM Judges with Adaptive Stability Detection](https://neurips.cc/virtual/2025/loc/san-diego/poster/117644)
* \[14] [When AIs Judge AIs: The Rise of Agent-as-a-Judge Evaluation for LLMs](https://arxiv.org/abs/2508.02994)

