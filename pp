
\documentclass[11pt]{article}
\usepackage[a4paper,margin=1in]{geometry}
\usepackage{amsmath,amssymb,mathtools}
\usepackage{booktabs,tabularx,array}
\usepackage{hyperref}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{enumitem}
\usepackage{tikz}
\usepackage{listings}
\lstset{basicstyle=\ttfamily\small,breaklines=true,frame=single}
\usepackage[margin=1in]{geometry}
\usepackage{amsmath,amssymb,amsthm}
\newtheorem{theorem}{Theorem}
\usepackage{mathtools}
\usepackage{booktabs}
\usepackage{algorithm}
\usepackage{algpseudocode}
\usepackage{microtype}
\usepackage{hyperref}
\hypersetup{colorlinks=true,linkcolor=blue,citecolor=blue,urlcolor=blue}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{enumitem}
\usepackage{tikz}
\usetikzlibrary{arrows.meta,calc,positioning}
\setlist[itemize]{noitemsep,topsep=2pt}
\setlist[enumerate]{noitemsep,topsep=2pt}

\title{The 2D Shortest Superstring Problem: Models, Heuristics and a Neural Solver Roadmap}
\author{ }
\date{\vspace{-5ex}}

\begin{document}
\maketitle

\begin{abstract}
We study the 2D Shortest Superstring problem: given a multiset of square tiles of size $n\times n$ drawn from a finite alphabet, place one translated copy of every tile on an integer grid so that overlapping cells agree and the side $m$ of the bounding square is minimized. This report gives a compact problem formulation, describes a simple \emph{greedy} placement heuristic, a practical Ant Colony Optimization (ACO) design, and a blueprint for a neural solver that can be used standalone or in hybrid pipelines. We list limitations of the current prototype and propose remedies (end-to-end training, symbol embeddings, curriculum learning).
\end{abstract}
\section{Problem Definition: 2D Shortest Superstring (2D--SSP)}
\label{sec:2d-ssp-definition}

\paragraph{Alphabet and 2D strings.}
Let $\Sigma$ be a finite alphabet. For positive integers $h,w \in \mathbb{N}$, a \emph{2D string} (or \emph{tile}) of height $h$ and width $w$ is an array $X \in \Sigma^{h \times w}$ with entries $X[i,j] \in \Sigma$ for row indices $i \in \{1,\dots,h\}$ and column indices $j \in \{1,\dots,w\}$. In this paper the input tiles are square of fixed size $n \times n$ unless noted otherwise.

\paragraph{Occurrences and containment.}
Given $A \in \Sigma^{H \times W}$ and $B \in \Sigma^{h \times w}$ with $h \le H$ and $w \le W$, we say that \emph{$B$ occurs in $A$ at position $(r,c)$} if
\[
  A[r+i-1,\; c+j-1] \;=\; B[i,j]
  \quad \text{for all } i \in \{1,\dots,h\},\; j \in \{1,\dots,w\},
\]
with $1 \le r \le H-h+1$ and $1 \le c \le W-w+1$. We say that \emph{$A$ contains $B$} if there exists some position $(r,c)$ at which $B$ occurs in $A$. When the input is a multiset, multiple copies of an identical tile must each occur (possibly at different positions).

\paragraph{Input.}
A finite multiset $\mathcal{T}=\{T_1,\dots,T_k\}$ of tiles with $T_\ell \in \Sigma^{n \times n}$.

\paragraph{Feasible superstring (canvas).}
A \emph{canvas} of side length $m$ is any $S \in \Sigma^{m \times m}$. The canvas $S$ is \emph{feasible} for $\mathcal{T}$ if $S$ contains every tile $T_\ell \in \mathcal{T}$ as an occurrence (i.e., each $T_\ell$ appears as a contiguous $n \times n$ subarray of $S$).

\paragraph{Optimization version (2D--SSP).}
Given $\mathcal{T}$, find a feasible canvas $S^\star \in \Sigma^{m^\star \times m^\star}$ with \emph{minimum side length}
\[
  m^\star \;=\; \min \{\, m \in \mathbb{N} \;:\; \exists S \in \Sigma^{m \times m} \text{ that contains all } T_\ell \in \mathcal{T} \,\}.
\]
Equivalently, one may view the objective as minimizing area $m^2$ since the canvas is square.

\paragraph{Decision version.}
Given $\mathcal{T}$ and an integer bound $m \in \mathbb{N}$, decide whether there exists a canvas $S \in \Sigma^{m \times m}$ that contains all tiles in $\mathcal{T}$.

\paragraph{Conventions and variants.}
Unless explicitly stated:
(i) tiles are used without rotation or reflection;
(ii) occurrences must lie fully within the $m \times m$ canvas (no wraparound);
(iii) overlapping occurrences are allowed provided all overlapping symbols agree.
Natural variants allow rotations/reflections of tiles, rectangular canvases $H \times W$ with objective $\min \max\{H,W\}$ or $\min HW$, or heterogeneous tile sizes $T_\ell \in \Sigma^{h_\ell \times w_\ell}$.

\paragraph{Informal analogy.}
In the classical (1D) shortest superstring problem, one seeks a shortest string containing each input string as a contiguous substring. Here, the goal is a smallest \emph{square} 2D array containing each input tile as a contiguous \emph{submatrix}.

\section{Problem Formulation}
The definition of 2D--SSP in Section~\ref{sec:2d-ssp-definition} views a solution as a
single $m \times m$ canvas that contains all input tiles as subarrays.  
We now reformulate this containment perspective into an explicit \emph{placement} model.

\paragraph{Placements.}
Let $\mathcal{V}$ be a set of $T$ tiles, each $v \in \mathcal{V}$ being an
$n \times n$ array over the alphabet $\mathcal{A}$.  
A \emph{placement} assigns to each tile $v$ an integer coordinate
$p_v = (x_v,y_v) \in \mathbb{Z}^2$, interpreted as the top--left corner of $v$
in the global grid.  
The placement is \emph{valid} if every overlapping cell is symbol-consistent:
\[
\forall u,v\in\mathcal{V},\;\forall (a,b) \text{ in the overlap region: } 
u[a,b] = v[a',b'],
\]
where $(a,b)$ are local indices in $u$ and $(a',b')$ are the corresponding indices in $v$ after translation.

\paragraph{Objective.}
Given a valid placement $\{p_v\}_{v \in \mathcal{V}}$, its \emph{bounding box}
is the smallest axis-aligned square that contains all placed tiles.
The optimization objective of 2D--SSP is to minimize the side length $m$ of this bounding box
(equivalently, to minimize its area $m^2$).

\paragraph{Constructive view via relative moves.}
Any feasible placement can be built incrementally by starting from a single tile
and repeatedly placing a new tile relative to one already placed.
Formally, a \emph{relative edge} is a tuple
\[
(u,v,i,j) \quad\text{meaning: place tile $v$ at } p_v = p_u + (i,j),
\]
where $u$ is already placed, $v$ is not yet placed, and $(i,j)\in\mathbb{Z}^2$
may be negative.  
Thus, a constructive solution can be described as an ordered sequence of such edges
that eventually assigns positions to all tiles.

\subsection{Relative Moves}
For each ordered pair $(u,v)$ we precompute \emph{feasible offsets}
\[
\Delta = (\Delta x,\Delta y), \quad |\Delta x|,|\Delta y|\le n-1,
\]
such that placing $v$ at $p_u+\Delta$ produces only consistent overlaps.
Each feasible offset is scored by its overlap size $\mathrm{ov}(u,v,\Delta)$.

\subsubsection{Augmenting candidates with adjacency}
Feasible overlaps alone may not suffice to guarantee connectivity of the placement.
Therefore, we augment the candidate offsets with all edge-adjacent
(non-overlapping) displacements
\[
\mathcal{A}_n \;=\; \{(\pm n,t): t\in[-(n{-}1),n{-}1]\}\;\cup\;\{(t,\pm n): t\in[-(n{-}1),n{-}1]\},
\]
and optionally also the four corners $\{(\pm n,\pm n)\}$ if point contacts are allowed.
For such adjacency offsets, we define $\mathrm{ov}(u,v,\Delta)=0$.

The final candidate set for pair $(u,v)$ is
\[
\mathcal{C}(u,v) \;=\; \operatorname{R}\!\big(u,v\big)\;\cup\;\mathcal{A}_n,
\]
and the pheromone tensor $\tau[u,v,\Delta]$ is defined only for $\Delta \in \mathcal{C}(u,v)$.
Since $|\mathcal{A}_n|=4(2n-1)$ (or $+4$ if corners are included),
the move space remains sparse yet complete.

\begin{theorem}[Completeness of neighbor-induced candidates]
Let $\mathcal{V}$ be a set of $n\times n$ tiles.
Consider any constructive procedure that, at each step, for every already placed tile $u$ and unplaced tile $v$, proposes all offsets that either
(i) yield a consistent overlap with $u$, or
(ii) are edge-adjacent to $u$.
Then some optimal placement can be reconstructed entirely from such proposals.
\end{theorem}

\begin{proof}[Proof sketch]
Take an optimal layout $\Pi^\star$ and rigidly translate connected components
until their contact graph is connected without enlarging the bounding box.
Select a spanning tree of this contact graph and place tiles following the tree order.
Whenever placing a child $v$ of a parent $u$, the realized offset
$\Delta^\star = p_v - p_u$ is either overlapping or edge-adjacent by construction,
so it belongs to the candidate set.
Induction over the tree shows that $\Pi^\star$ (or an equivalent optimal layout)
is reconstructible.
\end{proof}



\section{Greedy heuristic}
A practical greedy procedure proceeds as follows:
\begin{enumerate}
  \item Initialize by choosing an arbitrary seed tile $s$ and set $p_s=(0,0)$.
  \item While there are unplaced tiles:
  \begin{itemize}
    \item Enumerate \emph{feasible} candidate edges $(u,v,i,j)$ where $u$ is placed, $v$ unplaced, and placing $v$ at $p_u+(i,j)$ causes no symbol conflicts with already placed tiles.
    \item For each candidate compute $\Delta\mathrm{BBox}(u,v,i,j)$, the incremental increase in bounding-box side (or area). Break ties by preferring larger overlap (i.e. maximize the number of overlapping matching cells).
    \item Pick the candidate minimizing $\Delta\mathrm{BBox}$ (tie-breaker: maximal overlap) and commit the placement.
  \end{itemize}
\end{enumerate}

This simple rule is extremely cheap to compute and performs well on structured instances: by explicitly optimizing the local objective $\Delta\mathrm{BBox}$ it tends to keep the canvas compact. Pseudocode is given in Algorithm~\ref{alg:greedy}.

\begin{algorithm}
\caption{Greedy placement by minimal $\Delta\mathrm{BBox}$}
\label{alg:greedy}
\begin{algorithmic}[1]
\State Input: tiles $\mathcal{V}$, seed $s$
\State Place $s$ at $(0,0)$
\While{unplaced tiles remain}
  \State Build feasible candidate set $C=\{(u,v,i,j)\}$
  \ForAll{$c\in C$}
    \State compute $\Delta\mathrm{BBox}(c)$ and overlap$(c)$
  \EndFor
  \State choose $c^*=\arg\min\Delta\mathrm{BBox}$, break ties by max overlap
  \State commit placement from $c^*$
\EndWhile
\end{algorithmic}
\end{algorithm}

\section{Ant Colony Optimization (ACO)}
We outline a constructive ACO that uses sparse pheromone tables indexed by relative edge tuples. Let $\tau_{u,v,i,j}\ge0$ denote the pheromone for edge $(u,v,i,j)$ and let $\eta_{u,v,i,j}$ denote a local heuristic (e.g. number of overlapping cells between $u$ and $v$ when placed at $(i,j)$, possibly normalized).

At each construction step, given the set of placed tiles $P$ and unplaced tiles $U$, enumerate all feasible placements
\[C=\{(u,v,x,y) : u\in P, v\in U, \text{$v$ can be placed at }p_v=p_u+(x,y)\}\;.\]
For every candidate $(u,v,x,y)$ compute cumulative pheromone and heuristic contributions aggregated over all possible anchors $u$ that yield the same absolute placement of $v$:
\begin{align*}
\Phi(v, x,y) &= \sum_{u\in P} \tau_{u,v, i_{u}, j_{u}},\\
\Psi(v, x,y) &= \sum_{u\in P} \eta_{u,v, i_{u}, j_{u}},
\end{align*}
where $i_u,j_u$ are the relative offsets consistent with $p_u$ and $(x,y)$.
The sampling probability of candidate $(v,x,y)$ is then
\begin{equation*}
P(v,x,y) \propto \Phi(v,x,y)^{\alpha}\,\Psi(v,x,y)^{\beta},
\end{equation*}
with tunable exponents $\alpha,\beta>0$. After a complete construction the resulting canvas side $m$ yields a fitness; pheromones are then evaporated and reinforced along the used edges (standard ACO updates).

Key practical notes:
\begin{itemize}
  \item Use sparse storage for $\tau$ (only materialize edges observed during candidate enumeration).
  \item Design $\eta$ to reward larger overlaps and compact placements (e.g. $\eta=\#\text{overlap cells}+\lambda\cdot(1/\Delta\mathrm{BBox})$).
  \item Maintain a budget on candidate enumeration (e.g. only offsets within a radius around the current bounding box) to control runtime.
\end{itemize}
Algorithmic skeleton is in Algorithm~\ref{alg:aco}.

\begin{algorithm}
\caption{High-level ACO constructive loop}
\label{alg:aco}
\begin{algorithmic}[1]
\State Initialize pheromones $\tau$ (sparse), parameters $\alpha,\beta$, evaporation $\rho$
\For{each ant}
  \State Start with seed placement
  \While{unplaced tiles remain}
    \State enumerate feasible candidates $C$
    \State compute $\Phi,\Psi$ and sample $(v,x,y)$ with probability $P\propto\Phi^{\alpha}\Psi^{\beta}$
    \State commit placement
  \EndWhile
  \State evaluate canvas side $m$ and record edges used
\EndFor
\State update pheromones (evaporate + reinforce best solutions)
\end{algorithmic}
\end{algorithm}

\section{RL Model}

Below is a terse, formal description of the stepwise policy model used to score placement candidates.

\paragraph{Objects and inputs.} At each step the agent observes a rasterized partial layout $\mathcal{R}$, a set of remaining tile embeddings $\mathcal{T}=\{t_i\}_{i=1}^M$ with membership mask, and a candidate set $\mathcal{C}=\{(f_a,\,\tau_a)\}_{a=1}^A$ where each candidate pairs numeric features $f_a$ with an index $\tau_a$ pointing into $\mathcal{T}$.

\paragraph{Encoders and fusion.} Let
\[r = R(\mathcal{R})\in\mathbb{R}^{d},\qquad s = S(\mathcal{T})\in\mathbb{R}^{d},\]
where $R$ is a small CNN over the raster and $S$ is a permutation-invariant set encoder over tile embeddings. Fuse by a small MLP
\[e = F([r;s])\in\mathbb{R}^{d}.\]

\paragraph{Candidate tokens and scoring.} For each candidate $a$ gather the tile embedding $t_{\tau_a}$ and form
\[c_a = P([f_a; t_{\tau_a}])\in\mathbb{R}^{d},\]
with $P$ an MLP. Score candidates with a scorer $\phi:\mathbb{R}^d\times\mathbb{R}^d\to\mathbb{R}$:
\[\ell_a = \phi(e,c_a).\]
Apply the feasibility mask by setting masked logits to a large negative constant and normalize:
\[\pi(a\mid s) \propto \exp(\ell_a)\ (\text{masked}).\]
A scalar value $v=V(e)\in\mathbb{R}$ is predicted by a small MLP.

\section{Model Training}
\label{sec:training}

We train the policy network with entropy-regularized REINFORCE on episodic rollouts of the 2D--SSP environment. At each decision step the agent receives a masked set of candidate actions (feasible placements) and samples from the temperature-scaled softmax over valid logits.

\paragraph{State, action, reward.}
At a step $t$, the environment produces a batchable state summary $\mathbf{s}_t$ that includes (i) a raster view of the current canvas, (ii) the set of remaining tiles, and (iii) the candidate list $\mathcal{A}_t=\{a_t^{(1)},\dots,a_t^{(K_t)}\}$ with a Boolean mask $M_t\in\{0,1\}^{K_t}$. The policy outputs logits $\ell_t\in\mathbb{R}^{K_t}$.
We apply temperature $\tau>0$ and masking:
\[
\tilde \ell_t^{(k)} \;=\;
\begin{cases}
\ell_t^{(k)}/\tau, & M_t^{(k)}=1,\\
-\infty, & M_t^{(k)}=0,
\end{cases}
\qquad
\pi_\theta(a_t^{(k)}\mid \mathbf{s}_t)
=\frac{\exp(\tilde \ell_t^{(k)})}{\sum_{j:\,M_t^{(j)}=1}\exp(\tilde \ell_t^{(j)})}.
\]
We then sample $a_t\sim \pi_\theta(\cdot \mid \mathbf{s}_t)$. The per-step reward is a shaped proxy for canvas minimization:
\[
r_t \;=\; -\,\Delta m_t \;+\; \lambda\, H_t,
\]
where $\Delta m_t$ is the \emph{increment} in the current bounding-box side length if the chosen placement is applied (zero if unchanged), and $H_t$ is a heuristic overlap score of the chosen candidate (first channel of the candidate feature in our implementation). $\lambda\!\ge\!0$ is the overlap-bonus coefficient.

\paragraph{Objective with entropy regularization.}
For an episode of length $T$ with returns $G_t=\sum_{k=t}^{T} \gamma^{\,k-t} r_k$, we use a moving baseline $b\approx \mathbb{E}[G_1]$ to reduce variance and maximize:
\[
J(\theta)\;=\;\mathbb{E}\!\left[\sum_{t=1}^{T} \big(G_t-b\big)\,\log \pi_\theta(a_t\mid \mathbf{s}_t) \;+\; \beta\,\mathcal{H}\big(\pi_\theta(\cdot\mid \mathbf{s}_t)\big)\right],
\]
where $\mathcal{H}$ is the categorical entropy and $\beta\!\ge\!0$ is the entropy coefficient.

\begin{algorithm}[H]
\caption{\textsc{RolloutEpisode} (single environment)}
\label{alg:rollout}
\begin{algorithmic}[1]
\Require policy $\pi_\theta$, env $\mathcal{E}$, tile embeddings $E$, temperature $\tau$, max steps $T_{\max}$, overlap bonus $\lambda$
\State Reset env; $\mathcal{L}\leftarrow[]$, $\mathcal{R}\leftarrow[]$, $S_{\mathrm{ent}}\leftarrow 0$, $t\leftarrow0$
\While{not done and $t<T_{\max}$}
  \State $(\mathbf{s}_t, \mathcal{A}_t, M_t)\gets \textsc{BuildStepBatchFromEnv}(\mathcal{E}, E)$
  \If{$\neg \textsc{Any}(M_t)$} \textbf{break} \EndIf
  \State $\ell_t \gets f_\theta(\mathbf{s}_t)$ \Comment{forward pass}
  \State $\tilde \ell_t \gets \textsc{MaskAndScale}(\ell_t,M_t,\tau)$
  \State $p_t \gets \textsc{Softmax}(\tilde \ell_t)$,\quad
         $a_t \sim p_t$, \quad
         $\log\pi_t \gets \log p_t[a_t]$
  \State $S_{\mathrm{ent}} \gets S_{\mathrm{ent}} - \sum_k p_t^{(k)} \log p_t^{(k)}$
  \State $\Delta m_t \gets \textsc{BBoxIncreaseIfPlace}(a_t)$,\quad $H_t \gets \textsc{CandHeuristic}(a_t)$
  \State $r_t \gets -\Delta m_t + \lambda H_t$
  \State Append $\log\pi_t$ to $\mathcal{L}$; append $r_t$ to $\mathcal{R}$
  \State $\textsc{StepEnv}(\mathcal{E}, a_t)$;\quad $t\gets t+1$
\EndWhile
\State $m_{\mathrm{final}}\gets \textsc{LayoutBBoxSide}(\mathcal{E})$
\State \Return $\mathcal{L}$, $\mathcal{R}$, $m_{\mathrm{final}}$, $t$, $S_{\mathrm{ent}}$
\end{algorithmic}
\end{algorithm}

\paragraph{Returns and baseline.}
We compute discounted returns (from first-visit):
\[
G_t \;=\; r_t + \gamma r_{t+1} + \cdots + \gamma^{T-t} r_T,
\quad
b \leftarrow \alpha\, b + (1-\alpha)\,\overline{G}_1 \quad (\text{EMA with } \alpha\in[0,1)).
\]

\begin{algorithm}[H]
\caption{\textsc{TrainREINFORCE} (mini-batched over a fixed dataset)}
\label{alg:train}
\begin{algorithmic}[1]
\Require policy $\pi_\theta$, TileCNN, batch size $B$, dataset sizes $N_{\mathrm{train}},N_{\mathrm{val}}$, epochs $E$, lr, $\gamma$, $\beta$ (entropy coef), $\lambda$ (overlap bonus), $\tau$ (temperature)
\State Build datasets: $\{\mathcal{E}_i^{\mathrm{train}}\}_{i=1}^{N_{\mathrm{train}}}$ and $\{\mathcal{E}_j^{\mathrm{val}}\}_{j=1}^{N_{\mathrm{val}}}$
\State Precompute tile embeddings $\{E_i^{\mathrm{train}}\}$, $\{E_j^{\mathrm{val}}\}$ with TileCNN (frozen here)
\State Initialize optimizer; baseline $b\gets \text{None}$
\For{$\text{epoch}=1$ to $E$}
  \State Sample indices $\mathcal{I}\subset\{1,\dots,N_{\mathrm{train}}\}$ with $|\mathcal{I}|=B$
  \State $\mathcal{D}\leftarrow \emptyset$, $S_{\mathrm{ent}}\leftarrow 0$, \textsc{stats} $\leftarrow$ \textsc{zeros()}
  \For{$i\in\mathcal{I}$}
     \State $(\mathcal{L},\mathcal{R}, m_{\mathrm{fin}}, \text{steps}, S_{\mathrm{ent}}^{(i)}) \gets \textsc{RolloutEpisode}(\pi_\theta,\mathcal{E}_i^{\mathrm{train}},E_i^{\mathrm{train}},\tau,T_{\max},\lambda)$
     \State Update stats with $(m_{\mathrm{fin}},\text{steps})$; $S_{\mathrm{ent}} \gets S_{\mathrm{ent}} + S_{\mathrm{ent}}^{(i)}$
     \If{$|\mathcal{L}|>0$}
        \State $G \gets \textsc{DiscountedReturns}(\mathcal{R},\gamma)$
        \State Append $(\mathcal{L}, G)$ to $\mathcal{D}$
     \EndIf
  \EndFor
  \If{$|\mathcal{D}|=0$} \textbf{continue} \EndIf
  \State $\overline{G}_1 \gets \text{mean}\{G_1 : (\cdot,G)\in\mathcal{D}\}$
  \State $b \gets \begin{cases}
        \overline{G}_1, & b=\text{None}\\
        \alpha b + (1-\alpha)\overline{G}_1, & \text{otherwise}
      \end{cases}$
  \State \textbf{(Policy loss + entropy)} \\
  \hspace{1em} $L_{\mathrm{pol}} \gets 0$ \\
  \hspace{1em} \textbf{for each} $(\mathcal{L}, G)\in\mathcal{D}$ \textbf{do}
     \hspace{0.25em} $A \gets G - b$;\quad $L_{\mathrm{pol}} \gets L_{\mathrm{pol}} - \sum_{t} \mathcal{L}_t \cdot \text{stopgrad}(A_t)$
  \State $L \gets L_{\mathrm{pol}} - \beta \, S_{\mathrm{ent}}$
  \State Backprop $L$; clip gradients; optimizer step
  \State \textbf{(Validation every $k$ epochs)}: run greedy/soft evaluation on $\{\mathcal{E}_j^{\mathrm{val}}\}$ to report mean final side $\bar m$ and mean steps
\EndFor
\end{algorithmic}
\end{algorithm}

\paragraph{Implementation notes.}
(i) We set $-\infty$ in masked logits via a large negative constant in practice.
(ii) Temperature $\tau$ anneals exploration; $\beta$ encourages per-step entropy.
(iii) We use gradient clipping (e.g., $\ell_2$ norm $1.0$).
(iv) Datasets are fixed synthetic instances; each epoch samples a mini-batch with replacement.
(v) Validation runs a greedy (or low-temperature) decode to estimate the mean final side length.



We summarize limitations observed in the current prototype and possible fixes:
\begin{enumerate}
  \item \textbf{Fixed, precomputed tile embeddings.} Currently the TileCNN is initialized with random weights and used as a fixed feature map. This may cause the downstream model to depend primarily on geometric overlap statistics rather than semantic tile content. (Note: Already Fixed)\
  \textbf{Remedy:} fine-tune TileCNN end-to-end, or learn a small projection from tile one-hot channels to embeddings jointly with the rest of the model.

  \item \textbf{Fixed alphabet size.} The TileCNN expects a fixed channel dimension for symbols. For variable alphabets replace one-hot symbol channels with learned symbol embeddings (indexed by symbol ids) and aggregate them into the tile tensor; alternatively, token-based (transformer) encoders over sequences of symbols can handle dynamic vocabularies. Expect some performance degradation when alphabet size grows, but learned embeddings should mitigate it.

  \item \textbf{Static training regime (fixed $T,n,|\mathcal{A}|$).} Training on a single size limits generalization.\
  \textbf{Remedy:} curriculum training over increasing $T,n,|\mathcal{A}|$, data augmentation (random rotations/translations of tile layouts), and multi-task heads that normalize for $n$.
\end{enumerate}

\section{Conclusion}
We described compact, interoperable constructive paradigms for the 2D Shortest Superstring problem: a cheap greedy baseline, a scalable ACO with sparse pheromones and overlap-based heuristics, and a neural-solver blueprint suitable for hybridization. The most important next steps are: (1) end-to-end training of tile embeddings, (2) implementing symbol embeddings for variable alphabets, and (3) curriculum training to improve robustness across sizes.

\vspace{1em}
\noindent\textbf{Acknowledgements.} Implementation notes and experimental scripts are omitted; this report focuses on algorithms and design choices.

\end{document}
