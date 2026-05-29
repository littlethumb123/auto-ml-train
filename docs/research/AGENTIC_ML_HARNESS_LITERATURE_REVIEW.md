# Agentic ML Harnesses, Context Engineering, and Workflow Benchmarks

Date: 2026-04-17
d

## Scope

This review focuses on the part of the agentic-AI literature that is closest to:

- automated data science
- ML framing and experiment design
- model building and hyperparameter search
- evaluation and benchmark design
- harness or context-engineering choices around executable ML workflows

I intentionally separate three different things that are often mixed together:

1. benchmark suites for ML agents
2. end-to-end autonomous research or data-science systems
3. older AutoML systems that are not agentic in the LLM sense, but are direct harness predecessors

## Evidence policy

I used only source-backed records for the claims below:

- OpenAlex for title, year, venue/source, DOI, and abstract reconstruction when available
- arXiv abstract pages for directly quoted abstracts and repository links
- ACL Anthology for Agent Laboratory metadata and abstract
- Crossref for one missing citation venue string
- GitHub repository search metadata for repository existence, stars, licenses, update activity, and descriptions

Where a paper is an arXiv preprint rather than a peer-reviewed archival paper, I say so explicitly.

## Executive Summary

The literature has now split into a fairly clear stack.

- The strongest benchmark-oriented papers for agentic ML workflows are MLAgentBench, MLE-bench, and MLGym. These are the most useful if your research question is about harness design, context handling, or agent performance under controlled task suites.
- The strongest end-to-end workflow systems are DS-Agent, AutoKaggle, The AI Scientist, and Agent Laboratory. These are valuable because they expose real harness surfaces such as memory, case retrieval, code execution, debugging, report writing, and human intervention.
- CAAFE is narrower than the others, but it is important because it shows how LLM context can be tied directly to tabular feature engineering, which is one of the few papers that operationalizes semantic context in a traditional ML workflow.
- Classical AutoML systems such as auto-sklearn, TPOT, FLAML, AutoKeras, and Auto-PyTorch are still important. They are not agentic research systems, but they define the baseline harness logic that newer agentic systems either wrap, replace, or compete against.
- Benchmark coverage is strongest for experimentation and modeling. It is noticeably weaker for data ingestion governance, feature-store integration, deployment, monitoring, and post-deployment ML operations.

## 1. Literature Review

### 1.1 Benchmark-first and agentic ML workflow papers

#### 1. DS-Agent: Automated Data Science by Empowering Large Language Models with Case-Based Reasoning

- Verified source: arXiv 2402.17453, 2024. The arXiv page notes "Accepted by ICML 2024".
- What it does: Automates data-science tasks with an LLM agent that must understand requirements, build ML models, train them, and iterate.
- Harness design: The core harness is case-based reasoning. In the development stage, the system structures an automatic iteration pipeline that reuses expert knowledge from Kaggle and improves through feedback. In the deployment stage, it uses a simplified CBR paradigm to adapt past successful solutions for direct code generation.
- Evaluation: The abstract reports a 100% success rate in the development stage with GPT-4, a 36% average improvement in one-pass rate across alternative LLMs in deployment, and explicit per-run cost reporting.
- Why it matters: This is one of the clearest examples of an ML-specific agent harness where memory is not generic chat history but reusable experiment cases.

#### 2. Large Language Models for Automated Data Science: Introducing CAAFE for Context-Aware Automated Feature Engineering

- Verified source: arXiv 2305.03403, 2023.
- What it does: Uses an LLM to iteratively generate semantically meaningful tabular features from a dataset description.
- Harness design: The harness is narrow but important: dataset description plus feature-generation loop plus generated Python code plus textual explanation. It is one of the cleanest examples of context engineering for a classical ML subproblem.
- Evaluation: The abstract reports improvement on 11 of 14 datasets and mean ROC AUC improvement from 0.798 to 0.822.
- Why it matters: CAAFE shows how context can be operationalized as structured semantic prior rather than long conversational memory.

#### 3. MLAgentBench: Evaluating Language Agents on Machine Learning Experimentation

- Verified source: arXiv 2310.03302, initial submission 2023, revised 2024.
- What it does: Benchmarks whether language agents can perform ML experimentation.
- Harness design: The harness exposes filesystem operations, code writing, code execution, and output inspection. The paper states that the evaluated agent follows a ReAct-style framework.
- Evaluation: 13 tasks ranging from improving CIFAR-10 performance to newer research problems such as BabyLM. The abstract reports that the best Claude 3 Opus agent achieves 37.5% average success rate.
- Why it matters: MLAgentBench is one of the first benchmark suites that treats ML experimentation itself as the task, not just code generation.

#### 4. MLE-bench: Evaluating Machine Learning Agents on Machine Learning Engineering

- Verified source: arXiv 2410.07095, 2024. The arXiv page notes that the current version is the ICLR version.
- What it does: Measures how well AI agents perform ML engineering on Kaggle-style tasks.
- Harness design: The benchmark uses open-source agent scaffolds over curated Kaggle competitions. The environment stresses dataset preparation, model training, experiment execution, and competitive evaluation.
- Evaluation: 75 Kaggle competitions with human baselines derived from public leaderboards. The abstract reports that the best setup reaches at least Kaggle bronze level in 16.9% of competitions.
- Why it matters: This is currently the strongest benchmark for realistic ML engineering under external performance metrics.

#### 5. MLGym: A New Framework and Benchmark for Advancing AI Research Agents

- Verified source: arXiv 2502.14499, 2025.
- What it does: Introduces both a framework and a benchmark for AI research agents.
- Harness design: MLGym is explicitly framed as a Gym environment for ML tasks. It is designed to support both evaluation and future reinforcement-learning-based training of research agents.
- Evaluation: MLGym-Bench contains 13 diverse open-ended AI research tasks across computer vision, NLP, reinforcement learning, and game theory. The abstract says current frontier models mostly improve baselines by better hyperparameters, not by generating truly novel hypotheses or algorithms.
- Why it matters: This is the cleanest bridge between agent benchmarking and a trainable research-agent environment.

#### 6. AutoKaggle: A Multi-Agent Framework for Autonomous Data Science Competitions

- Verified source: arXiv 2410.20424, 2024.
- What it does: Targets daily tabular-data workflows and Kaggle-style competitions with a collaborative multi-agent system.
- Harness design: Iterative code execution, debugging, and comprehensive unit testing. The framework also exposes customizable workflows and explicit user intervention points. It uses a universal toolkit for data cleaning, feature engineering, and modeling.
- Evaluation: 8 Kaggle competitions. The abstract reports a validation submission rate of 0.85 and a comprehensive score of 0.82.
- Why it matters: AutoKaggle is one of the strongest papers if your interest is not pure benchmark design but practical workflow harness design for tabular ML.

#### 7. The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery

- Verified source: arXiv 2408.06292, 2024.
- What it does: Proposes a full pipeline for automated scientific discovery in ML.
- Harness design: Idea generation, code writing, experiment execution, result visualization, paper writing, and simulated review. The workflow is designed to be repeatable in an open-ended loop.
- Evaluation: Demonstrated on diffusion modeling, transformer-based language modeling, and learning dynamics. The abstract reports less than $15 per generated paper and an automated reviewer that approaches human scoring quality.
- Why it matters: This paper is broader than benchmark papers, but it is a direct reference for end-to-end research harnesses and staged context transfer across the full research lifecycle.

#### 8. Agent Laboratory: Using LLM Agents as Research Assistants

- Verified source: Findings of ACL EMNLP 2025, DOI 10.18653/v1/2025.findings-emnlp.320.
- What it does: Accepts a human research idea and autonomously moves through literature review, experimentation, and report writing.
- Harness design: Three-stage workflow with opportunities for human guidance at each stage. The output includes both code repository artifacts and a research report.
- Evaluation: The abstract reports that o1-preview produced the best outcomes, that human involvement improves quality, and that the system reduced research expenses by 84% relative to previous autonomous research methods.
- Why it matters: Agent Laboratory is one of the clearest workflow harnesses for human-guided but largely autonomous ML research execution.

### 1.2 Pre-agentic and precursor ML automation papers

These papers matter because they define the search, pipeline, and resource-management harnesses that modern agentic systems inherit or replace.

#### 9. Efficient and Robust Automated Machine Learning

- Verified source: NeurIPS 2015.
- What it does: Introduces auto-sklearn as a robust AutoML system over scikit-learn.
- Harness design: Structured hypothesis space, Bayesian optimization, meta-learning from prior datasets, and ensemble construction from evaluated models.
- Evaluation: The abstract reports over 100 diverse datasets and outperformance over prior AutoML methods, along with success in the first phase of the ChaLearn AutoML challenge.
- Why it matters: This is a canonical non-agentic harness for algorithm selection, preprocessing, and hyperparameter optimization.

#### 10. Evaluation of a Tree-based Pipeline Optimization Tool for Automating Data Science

- Verified source: Proceedings of the Genetic and Evolutionary Computation Conference 2016, DOI 10.1145/2908812.2908918.
- What it does: Introduces TPOT and frames pipeline design itself as an optimization problem.
- Harness design: Tree-based pipeline search with Pareto optimization to balance accuracy and complexity.
- Evaluation: The abstract says TPOT was demonstrated on simulated and real-world benchmark datasets and showed significant improvement over a basic ML analysis while reducing user effort.
- Why it matters: TPOT is a direct predecessor to agentic systems that search over pipeline structures, except TPOT uses evolutionary search instead of an LLM planner.

#### 11. FLAML: A Fast and Lightweight AutoML Library

- Verified source: Proceedings of Machine Learning and Systems, 2021.
- What it does: Optimizes learner and hyperparameter selection under low compute budgets.
- Harness design: Trial-cost-aware adaptive search; the central harness principle is budget-aware automation rather than open-ended reasoning.
- Evaluation: The abstract reports strong performance on open-source AutoML benchmarks under equal or much smaller budget constraints than competing libraries.
- Why it matters: FLAML is a useful contrast case because many agentic ML systems still ignore explicit budget-aware optimization, even though FLAML shows it is central to practical automation.

## 2. Harness and Context-Engineering Patterns in ML Workflows

Across the papers above, the most important harness design surfaces are not generic chat-agent tricks. They are ML-specific control surfaces.

### 2.1 The recurring harness primitives

#### A. Externalized task memory

- DS-Agent uses case-based reasoning over prior successful solutions.
- AutoKaggle uses a reusable toolkit of validated functions.
- CAAFE uses dataset descriptions as structured context rather than unbounded conversation.
- The AI Scientist and Agent Laboratory externalize artifacts such as code, reports, and review outputs as part of the loop.

The important point is that useful ML agent memory is usually artifact-centric, not just token-history-centric.

#### B. Executable experimental substrate

- MLAgentBench, MLE-bench, AutoKaggle, MLGym, The AI Scientist, and Agent Laboratory all rely on real code execution.
- The common substrate is some combination of files, shell commands, training scripts, metric outputs, and debugging traces.

This is the defining difference between an "ML agent" and a general-purpose chat agent discussing ML.

#### C. Explicit evaluation loop

- Kaggle submission score in MLE-bench and AutoKaggle.
- task success rate in MLAgentBench.
- benchmark improvement over provided baselines in MLGym.
- tabular metric lift in CAAFE.
- paper or reviewer score in The AI Scientist and Agent Laboratory.

The best systems do not rely on an LLM judge alone. They bind the agent to an external metric.

#### D. Stage-structured workflows

- Agent Laboratory has literature review, experimentation, and report writing.
- The AI Scientist has idea generation, implementation, experimentation, paper writing, and simulated review.
- DS-Agent separates development and deployment stages.
- AutoKaggle separates phases while allowing user intervention.

Stage separation is a strong context-engineering mechanism because it narrows the active context per phase.

#### E. Human-intervention boundary

- AutoKaggle explicitly allows intervention at each phase.
- Agent Laboratory includes researcher feedback during the process.
- The AI Scientist and DS-Agent are more autonomous but still expose cost/performance checkpoints.

The literature suggests that ML workflow harnesses are often strongest when they are not fully closed-loop.

### 2.2 What is still weak in current harness design

- Most papers focus on modeling and experimentation, not real ingestion pipelines or production deployment.
- Feature-store integration, data lineage, governance, and deployment rollback are largely absent.
- Many evaluations still depend on benchmark suites that are narrower than real enterprise ML.
- Budget constraints are reported in some papers, but compute-aware planning is still underdeveloped relative to classical AutoML.
- Context engineering is usually implicit in workflow decomposition, artifact retrieval, or case reuse. Very few papers isolate context-management variables experimentally in the way benchmark design papers do.

## 3. Benchmark and Task Taxonomy for Agentic ML Workflows

This section answers the next natural question after the literature review: which tasks are actually being benchmarked, and which papers are true benchmarks versus one-off systems?

### 3.1 Reusable benchmark suites

#### MLAgentBench

- Type: benchmark suite
- Task family: ML experimentation
- Reported scale: 13 tasks
- Example task style from abstract: improving CIFAR-10 performance; BabyLM-style research problems
- Evaluation signal: task success rate
- Best use: studying planning, experiment iteration, code execution, and result interpretation

#### MLE-bench

- Type: benchmark suite
- Task family: ML engineering via Kaggle competitions
- Reported scale: 75 competitions
- Evaluation signal: public-leaderboard-based human baselines; bronze-medal threshold
- Best use: studying realistic tabular and competition-style ML engineering under strict external metrics

#### MLGym-Bench

- Type: benchmark suite plus training environment
- Task family: open-ended AI research tasks
- Reported scale: 13 tasks
- Domains: CV, NLP, RL, and game theory
- Evaluation signal: improvement over given baselines on research tasks
- Best use: studying research-agent training and benchmarking in a Gym-style environment

### 3.2 One-off or paper-specific workflow evaluations

These are highly relevant, but they are not general-purpose shared benchmarks in the same sense.

#### DS-Agent

- Uses Kaggle-derived expert knowledge and staged evaluation.
- Best read as a system paper with an ML workflow harness, not as a community benchmark.

#### AutoKaggle

- Evaluated on 8 Kaggle competitions.
- Best read as a multi-agent data science workflow paper with competition evaluation.

#### The AI Scientist

- Evaluated on three ML subfields plus automated reviewing.
- Best read as an autonomous research workflow paper, not as a standardized benchmark suite.

#### Agent Laboratory

- Evaluated through research-quality outcomes, human feedback, and cost reduction.
- Best read as a research-assistant workflow system with evaluation protocol, not a task benchmark suite.

#### CAAFE

- Evaluated on 14 tabular datasets.
- Best read as a specialized feature-engineering benchmarked method rather than a full workflow benchmark.

### 3.3 Benchmark families that recur across the literature

#### A. Kaggle or competition-style tabular ML

Used by or strongly related to:

- DS-Agent
- AutoKaggle
- MLE-bench

Why it matters:

- strong external metric
- realistic pressure on feature engineering and model iteration
- easier to compare against human baselines

Main weakness:

- over-represents leaderboard optimization and under-represents enterprise data constraints

#### B. Open-ended ML experimentation

Used by or strongly related to:

- MLAgentBench
- MLGym

Why it matters:

- captures experiment design and iteration rather than only final submission score
- better fit for harness research on planning, memory, and execution loops

Main weakness:

- harder to standardize than Kaggle-style evaluation

#### C. End-to-end autonomous research workflows

Used by or strongly related to:

- The AI Scientist
- Agent Laboratory

Why it matters:

- covers the broadest workflow surface, from literature to report writing

Main weakness:

- evaluation is broader and less standardized than benchmark suites such as MLE-bench

#### D. Narrow but important subworkflow benchmarks

Used by or strongly related to:

- CAAFE
- classical AutoML systems such as auto-sklearn, TPOT, and FLAML

Why it matters:

- these systems isolate one part of the ML workflow, which often makes methodological claims cleaner

Main weakness:

- they do not capture full agentic workflow complexity

## 4. Which Papers Best Match Your Specific Interest in Harness Design

If the primary question is "how should I design a harness for ML framing, modeling, and evaluation?", the highest-value papers are not all equal.

### Highest value for benchmark design

1. MLE-bench
2. MLAgentBench
3. MLGym

These are the most reusable if you want to compare harness variants under a common task set.

### Highest value for context-engineered workflow design

1. DS-Agent
2. AutoKaggle
3. Agent Laboratory
4. The AI Scientist
5. CAAFE

These are the most useful if you want to study how artifact memory, staged workflows, code execution, and human intervention are wired into the agent harness.

### Highest value as non-agentic baselines or predecessors

1. auto-sklearn / Efficient and Robust Automated Machine Learning
2. TPOT / Evaluation of a Tree-based Pipeline Optimization Tool for Automating Data Science
3. FLAML

These are essential because they define what good automation looked like before LLM agents.

## 5. GitHub Project Map

GitHub metadata below was checked via GitHub repository search on 2026-04-17 or 2026-04-18 UTC.

### 5.1 Core agentic ML and research repositories

1. snap-stanford/MLAgentBench
  - URL: [https://github.com/snap-stanford/MLAgentBench](https://github.com/snap-stanford/MLAgentBench)
  - Stars: 338
  - License: MIT
  - Last updated in GitHub metadata: 2026-04-16
  - Why it matters: benchmark implementation for ML experimentation agents
2. openai/mle-bench
  - URL: [https://github.com/openai/mle-bench](https://github.com/openai/mle-bench)
  - Stars: 1472
  - License: NOASSERTION in GitHub metadata
  - Last updated in GitHub metadata: 2026-04-18
  - Why it matters: strongest public Kaggle-style ML engineering benchmark for agents
3. facebookresearch/MLGym
  - URL: [https://github.com/facebookresearch/MLGym](https://github.com/facebookresearch/MLGym)
  - Stars: 594
  - License: NOASSERTION in GitHub metadata
  - Last updated in GitHub metadata: 2026-04-15
  - Why it matters: Gym-style environment and benchmark for AI research agents
4. multimodal-art-projection/AutoKaggle
  - URL: [https://github.com/multimodal-art-projection/AutoKaggle](https://github.com/multimodal-art-projection/AutoKaggle)
  - Stars: 290
  - License: Apache-2.0
  - Last updated in GitHub metadata: 2026-04-07
  - Why it matters: practical multi-agent tabular data-science workflow system
5. guosyjlu/DS-Agent
  - URL: [https://github.com/guosyjlu/DS-Agent](https://github.com/guosyjlu/DS-Agent)
  - Stars: 233
  - License: not asserted in the GitHub metadata captured here
  - Last updated in GitHub metadata: 2026-04-04
  - Why it matters: case-based reasoning harness for automated data science
6. SakanaAI/AI-Scientist
  - URL: [https://github.com/SakanaAI/AI-Scientist](https://github.com/SakanaAI/AI-Scientist)
  - Stars: 13290
  - License: NOASSERTION in GitHub metadata
  - Last updated in GitHub metadata: 2026-04-18
  - Why it matters: flagship end-to-end autonomous ML research workflow implementation
7. SamuelSchmidgall/AgentLaboratory
  - URL: [https://github.com/SamuelSchmidgall/AgentLaboratory](https://github.com/SamuelSchmidgall/AgentLaboratory)
  - Stars: 5512
  - License: MIT
  - Last updated in GitHub metadata: 2026-04-17
  - Why it matters: public implementation of staged autonomous research-assistant workflow
8. noahho/CAAFE
  - URL: [https://github.com/noahho/CAAFE](https://github.com/noahho/CAAFE)
  - Stars: 187
  - License: NOASSERTION in GitHub metadata
  - Last updated in GitHub metadata: 2026-04-15
  - Why it matters: focused implementation of context-aware tabular feature engineering

### 5.2 Classical AutoML and harness predecessor repositories

1. automl/auto-sklearn
  - URL: [https://github.com/automl/auto-sklearn](https://github.com/automl/auto-sklearn)
  - Stars: 8081
  - License: BSD-3-Clause
  - Last updated in GitHub metadata: 2026-04-12
  - Why it matters: canonical AutoML pipeline and hyperparameter optimization baseline
2. EpistasisLab/tpot
  - URL: [https://github.com/EpistasisLab/tpot](https://github.com/EpistasisLab/tpot)
    - Stars: 10042
    - License: LGPL-3.0
    - Last updated in GitHub metadata: 2026-04-16
    - Why it matters: pipeline-structure optimization baseline with strong relevance to agentic pipeline search
3. microsoft/FLAML
  - URL: [https://github.com/microsoft/FLAML](https://github.com/microsoft/FLAML)
    - Stars: 4332
    - License: MIT
    - Last updated in GitHub metadata: 2026-04-17
    - Why it matters: budget-aware AutoML baseline that many agentic systems still fail to match in efficiency discipline
4. keras-team/autokeras
  - URL: [https://github.com/keras-team/autokeras](https://github.com/keras-team/autokeras)
    - Stars: 9315
    - License: Apache-2.0
    - Last updated in GitHub metadata: 2026-04-17
    - Why it matters: deep-learning AutoML baseline and NAS-adjacent predecessor
5. automl/Auto-PyTorch
  - URL: [https://github.com/automl/Auto-PyTorch](https://github.com/automl/Auto-PyTorch)
    - Stars: 2536
    - License: Apache-2.0
    - Last updated in GitHub metadata: 2026-04-18
    - Why it matters: deep-learning AutoML baseline for architecture and hyperparameter automation in PyTorch

## 6. Practical Synthesis for Future Harness Research

If you want to design or evaluate a new harness for ML agents, the literature suggests a layered benchmark strategy rather than a single benchmark.

### Layer 1: narrow, clean subworkflow evaluation

- Use CAAFE-like feature-engineering tasks or classical AutoML baselines.
- Goal: isolate whether the harness improves one component such as feature generation, search efficiency, or pipeline construction.

### Layer 2: benchmarked ML experimentation

- Use MLAgentBench.
- Goal: study planning, iteration, error recovery, and code-execution loops under controlled ML tasks.

### Layer 3: realistic external-score engineering

- Use MLE-bench and, secondarily, AutoKaggle-style Kaggle tasks.
- Goal: test whether the harness survives real leaderboard-style optimization pressure.

### Layer 4: open-ended research workflows

- Use MLGym, The AI Scientist, and Agent Laboratory.
- Goal: study whether a harness can support ideation, experiment design, and artifact production over long horizons.

This layered view is important because no current benchmark alone covers the full ML lifecycle from ingestion to deployment.

## 7. Bottom Line

The field is no longer missing agentic ML papers. It is missing cleanly connected harness research across levels of abstraction.

- MLE-bench, MLAgentBench, and MLGym are the best benchmark-centric anchors.
- DS-Agent, AutoKaggle, Agent Laboratory, The AI Scientist, and CAAFE are the best harness-design case studies.
- auto-sklearn, TPOT, FLAML, AutoKeras, and Auto-PyTorch remain essential baselines because they embody mature automation logic that agentic systems should not ignore.

If your next step is a research program on context engineering for ML agents, the strongest design move is not to start from a generic coding agent benchmark. It is to compare harness variants across at least one benchmark from each of these strata:

1. tabular or feature-engineering tasks
2. ML experimentation tasks
3. Kaggle-style engineering tasks
4. open-ended research tasks

That is the smallest evaluation stack that reflects what the literature actually supports today.

## 8. Verified Sources

### Papers and abstracts

1. DS-Agent: Automated Data Science by Empowering Large Language Models with Case-Based Reasoning. arXiv:2402.17453. [https://arxiv.org/abs/2402.17453](https://arxiv.org/abs/2402.17453)
2. Large Language Models for Automated Data Science: Introducing CAAFE for Context-Aware Automated Feature Engineering. arXiv:2305.03403. [https://arxiv.org/abs/2305.03403](https://arxiv.org/abs/2305.03403)
3. MLAgentBench: Evaluating Language Agents on Machine Learning Experimentation. arXiv:2310.03302. [https://arxiv.org/abs/2310.03302](https://arxiv.org/abs/2310.03302)
4. MLE-bench: Evaluating Machine Learning Agents on Machine Learning Engineering. arXiv:2410.07095. [https://arxiv.org/abs/2410.07095](https://arxiv.org/abs/2410.07095)
5. MLGym: A New Framework and Benchmark for Advancing AI Research Agents. arXiv:2502.14499. [https://arxiv.org/abs/2502.14499](https://arxiv.org/abs/2502.14499)
6. AutoKaggle: A Multi-Agent Framework for Autonomous Data Science Competitions. arXiv:2410.20424. [https://arxiv.org/abs/2410.20424](https://arxiv.org/abs/2410.20424)
7. The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery. arXiv:2408.06292. [https://arxiv.org/abs/2408.06292](https://arxiv.org/abs/2408.06292)
8. Agent Laboratory: Using LLM Agents as Research Assistants. ACL Anthology / Findings of EMNLP 2025. [https://aclanthology.org/2025.findings-emnlp.320/](https://aclanthology.org/2025.findings-emnlp.320/)
9. Efficient and Robust Automated Machine Learning. NeurIPS 2015. OpenAlex record verified during review.
10. Evaluation of a Tree-based Pipeline Optimization Tool for Automating Data Science. GECCO 2016. DOI: 10.1145/2908812.2908918
11. FLAML: A Fast and Lightweight AutoML Library. Proceedings of Machine Learning and Systems, 2021. OpenAlex record verified during review.

### GitHub repositories

1. [https://github.com/snap-stanford/MLAgentBench](https://github.com/snap-stanford/MLAgentBench)
2. [https://github.com/openai/mle-bench](https://github.com/openai/mle-bench)
3. [https://github.com/facebookresearch/MLGym](https://github.com/facebookresearch/MLGym)
4. [https://github.com/multimodal-art-projection/AutoKaggle](https://github.com/multimodal-art-projection/AutoKaggle)
5. [https://github.com/guosyjlu/DS-Agent](https://github.com/guosyjlu/DS-Agent)
6. [https://github.com/SakanaAI/AI-Scientist](https://github.com/SakanaAI/AI-Scientist)
7. [https://github.com/SamuelSchmidgall/AgentLaboratory](https://github.com/SamuelSchmidgall/AgentLaboratory)
8. [https://github.com/noahho/CAAFE](https://github.com/noahho/CAAFE)
9. [https://github.com/automl/auto-sklearn](https://github.com/automl/auto-sklearn)
10. [https://github.com/EpistasisLab/tpot](https://github.com/EpistasisLab/tpot)
11. [https://github.com/microsoft/FLAML](https://github.com/microsoft/FLAML)
12. [https://github.com/keras-team/autokeras](https://github.com/keras-team/autokeras)
13. [https://github.com/automl/Auto-PyTorch](https://github.com/automl/Auto-PyTorch)

