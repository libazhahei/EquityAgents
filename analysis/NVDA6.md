# Google TPU V8 Vs. Nvidia: How Inference Is Rewriting The AI Market
Jun 08, 2026, 3:49 AM ETAlphabet Inc. (GOOGL) Stock, NVDA Stock, GOOG:CA Stock, GOOG Stock
# Summary
Google announced that it will begin selling TPUs to select third-party data center operators, marking the company's formal entrance into the merchant AI accelerator market where Nvidia dominates.
The share of AI inference workloads is rising; the economics of custom silicon are increasingly difficult to ignore, and Nvidia may be facing a Rubin delay.
The large coherent shared memory of TPU pods is a key feature that Google is banking on to differentiate from Nvidia systems.
Google (GOOGL) blew the doors off with its latest earnings report—cloud growth rapidly accelerated, margins expanded, and backlog soared 400% YoY to $462 billion. However, the quarter's most pivotal development wasn't in the financials; rather, it came from a strategic announcement.

# Investment Thesis
In April, Google announced it would begin selling its TPUs to select third-party data center operators, which is something the market has anticipated for nearly a decade. The TPU-versus-Nvidia-GPU debate has long fueled both bulls and bears; yet it may finally carry real stakes. Google's announcement is far from a coincidence—it is driven by several converging factors that make now the right moment to move.

As hyperscalers look to monetize their models, AI workloads are expanding from training to inference. This changes the focus away from accumulating expensive compute to a very different goal, which is lowering cost per token in order to scale inference economically.

In a previous article covering Google's TPUv7, we stated: “[...] custom silicon's cost advantages and ability to drive lower inference serving costs at scale create a strong value proposition for Big Tech.” Building on this, NVIDIA (NVDA) may be facing a Rubin delay, which opens a window of opportunity for Google to make the case for diversification beyond a single vendor for AI accelerators.

Below, we look at how Google's entrance into the merchant AI accelerator market sits at the center of three converging trends - and how the newly released TPU v8 generation positions custom silicon to meet the moment, giving Google a fighting chance against Nvidia.

# The Shift From AI Training to Inference: Why It Opens a Window of Opportunity for Google
To understand why the market is opening up for more players, we should first discuss why inference is becoming the dominant AI workload—and what this means for Nvidia.

Training frontier models is a discrete, multi-month event with a clear beginning and end. By contrast, inference is the revenue-generating phase and thus runs continuously with no ending point. Both training and inference workloads will continue to grow as labs build better models and monetize them. However, the always-on nature of inference will result in inference being the higher volume workload over time.

According to industry analysts, inference could take the larger share as soon as 2027. McKinsey estimates that in 2026, 31.2 GWs of data center demand will be allocated to training, and 31.2 GWs will be allocated to inference—an even 50/50 split. However, by 2027, inference becomes the larger share. By 2030, inference accounts for 93.3 GWs of demand, compared to training's 62.2 GWs—or a 60/40 split.

# Google TPU v8 Explained: 8i vs 8t and the Inference Advantage

At Cloud Next in late April, Google unveiled its latest TPU v8 in two configurations—the training-optimized 8t and the inference-optimized 8i. Notably, the Ironwood TPU v7 was the first TPU optimized for inference, but v8 marks the first time that the architecture has been split for two distinct purposes. As Google looks to capitalize on inference becoming the primary AI workload, splitting the v8 into two separate chips allows it to target this part of the market more effectively.

# TPU v8 Architecture: Why Google Split Training and Inference
With the 8i, Google is positioning itself to beat out Nvidia on one key aspect—coherent shared memory, a key anchor in improving inference efficiency.

While the 8i's pod size only scales 4.5X over Ironwood's 256-TPU pod to 1,152 TPUs per pod, pod-level HBM capacity increases by 7X to 331.8 TB versus 49.2 TB with Ironwood. Yet the key here is that this HBM capacity is coherent across the pod, across all 1,152 chips.

This is arguably the most critical point to understand surrounding Google's architectural advantage with the 8i, that this 331.8 TB of memory is shared across the entire pod over Google's inter-chip interconnect (ICI). ICI is similar to Nvidia's NVLink, with both allowing for the fastest chip-to-chip memory access within a pod. Compare this to Nvidia's NVL72, where true memory coherency only extends at rack scale across 72 GPUs and just 20.7TB of HBM. Scaling out to 1,152 of Nvidia's GPUs would span 16 racks, yet memory does not become a unified pool shared across the entire cluster.

By keeping the maximum amount of memory in a shared domain with the TPU 8i, large frontier models with long context windows can run with minimal latency.

# How TPU v8i Lowers Cost Per Token: SRAM and Boardfly
Several other key decisions reinforce the 8i's inference capabilities—pursuant to the ultimate goal of increasing inference efficiency by reducing latency, helping reduce cost per token as inference and agentic AI expand. These include boosting SRAM capacity per chip and introducing a new networking topology, dubbed Boardfly.

SRAM capacity is where Google is driving latency improvements at the chip level, increasing on-chip SRAM by 3X to 384MB for the 8i. SRAM is the fastest memory available to a chip, and the larger pool allows more of the chip's working memory, or KV cache, to stay on the fastest tier possible. In doing so, latency falls as the KV cache does not have to be retrieved from slower HBM. With 1,152 chips, the pod's total SRAM capacity is 432 GB.

Google's new Boardfly topology is its second lever in reducing latency. With Boardfly, Google connects 'building blocks' of four TPUs into boards, consisting of eight building blocks, that are then fully linked together as one pod. This is achieved via direct optical long-haul links, flattening the topology and reducing networking hops for any chip-to-chip communication from 16 hops to just seven. Google says this reduction in hops drives a “50% improvement in latency for communication-intensive workloads.”

As stated, the result of these improvements is lowering the 8i's cost per token. In line with this, Google notes that TPU 8i delivers up to an 80% performance-per-dollar improvement over the Ironwood TPU, particularly at low-latency targets for large MoE models. The 8i's deployment would compound the already significant serving cost reductions Google achieved in 2025. Last quarter, Google's CEO stated there was a 78% reduction in Gemini serving unit costs in 2025.

As chips spend less time sitting idle, Google—or any other TPU operator—can process more tokens at the same price. This strikes at the core of inference economics—minimizing the cost per token.

Deploying agentic AI within enterprises dramatically increases the need for memory in comparison to chatbots. Agents can act autonomously, performing complex multi-step tasks, drawing from organization-specific workflows, policies, and data—all of which require increased memory. Overall, Nvidia notes that agentic systems consume up to 15X more tokens than traditional AI applications. As token consumption vastly increases, lowering cost per token is critical to scaling agentic AI efficiently.

# Nvidia Prepares to Answer on Inference
While Google is deploying an inference-optimized TPU that warrants attention, from its ability to offer 331.8TB of shared coherent memory at pod level alongside other topology and architectural optimizations to improve inference efficiency, Nvidia remains the world's best chip designer and will not simply lay down and concede the inference market.

On that note, Nvidia is moving quickly with a different approach via its 256-chip Groq LPX rack, leveraging Groq's SRAM-based design to accelerate inference-based workloads via 'disaggregation' at rack scale. As covered in our free newsletter, Nvidia Stock to See New Growth Catalyst; 35X Faster AI with Groq 3 LPX, disaggregation refers to splitting up the two-step process of token generation, prefill and decode, and allocating each step to the hardware best designed for the task—prefill goes to compute-heavy Rubin GPUs, and memory and KV-cache intensive decode to the LPX rack.

Nvidia CEO Jensen Huang stated that combining the two co-designed racks can deliver up to 35X higher throughput per MW on trillion-parameter LLMs, with these throughput gains most evident on high token rate applications, such as real-time AI agent communication.

Naturally, there will be architectural differences between custom silicon and GPUs, such as the TPU 8i leveraging on-chip SRAM, yet the key takeaway is that Nvidia is moving ahead with a new strategy. The strategy, in a nutshell, is to offer seven co-designed chips that offload tasks to specialized hardware and optimize inference at the rack/system level versus the chip level.

Nvidia is the world's best AI chip design company, and all the above plus other incoming rapid changes to the company's product roadmap are something to keep a close eye on.

For more information on why Nvidia's CUDA moat matters less with inference, read our analysis here: Nvidia's $20 Trillion Thesis Is Intact - My 2026 Allocation Isn't.

# How Lower Token Costs Are Driving Google Cloud Growth and Margins
In Q1 2026, Google Cloud put up a hallmark performance. Revenue came in at $20 billion, with growth accelerating to 63% YoY. This was nearly double the 32% growth seen in Q2 2025 and 15 percentage points higher than the 48% growth seen in Q4 2025. Cloud backlog also hit $462 billion, up 400% YoY and 90.3% QoQ, signaling both the massive scale and acceleration of demand.

However, just as important was the huge expansion in Cloud operating margin. The figure moved up to 32.9%, a 15.1 percentage point expansion YoY and a 2.8 percentage point expansion QoQ.

# Gemini vs GPT vs Claude: Token Pricing Comparison
Connecting back to the TPU discussion, lowering token costs is key to Google Cloud's success. By keeping costs low, Google can attract more developers to Gemini, generating more cloud revenue. Gemini 3.1 Pro Preview, Anthropic's Claude Opus 4.7, and OpenAI's GPT-5.5 are widely considered frontier models—but data from Artificial Analysis indicates that Google has a very significant cost advantage.

The blended price per 1M tokens that customers pay on Gemini 3.1 is approximately $1.74. This is around 58% lower than Claude 4.7 and 60% lower than GPT 5.5. Additionally, this difference comes even as Google increased the per-token cost of Gemini 3.1 Pro Preview by 30% over Gemini 2.5 Pro.

