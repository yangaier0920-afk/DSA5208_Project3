# A: numerical problem, serial method and convergence — draft

Prepared 1 November 2026. The mathematical and historical-baseline sections are
ready for integration. New execution evidence currently consists of Windows
local basic checks; the planned Vanda numerical study has not been executed.

## Problem and discretization

We solve −Δu=f on Ω=(0,1)³ with Dirichlet boundary u=x+2y+3z and zero initial
interior values. The manufactured solution and source are

\[
u^*=x+2y+3z+\sin(\pi x)\sin(2\pi y)\sin(3\pi z),\quad
f=14\pi^2\sin(\pi x)\sin(2\pi y)\sin(3\pi z).
\]

The directional frequencies and coefficients differ. Each direction contains
n_d interior points with h_d=1/(n_d+1); boundary points are additional.
Using double precision, a seven-point central difference and a_d=1/h_d² gives

\[
u^{k+1}_{i,j,l}=
\frac{a_x(u^k_{i-1,j,l}+u^k_{i+1,j,l})+
a_y(u^k_{i,j-1,l}+u^k_{i,j+1,l})+
a_z(u^k_{i,j,l-1}+u^k_{i,j,l+1})+f_{i,j,l}}
{2(a_x+a_y+a_z)}.
\]

Two arrays ensure that every update reads the previous iteration.
Both arrays retain the physical boundary. The source is computed before
iteration. The independent serial entry point is jacobi_numerics.cpp.

## Fixed work and convergence

Fixed-work mode performs exactly K iterations (K=1000 for the planned study),
with initial and final residuals outside timing and no per-iteration update
maximum reduction. Solve mode evaluates the true interior residual r(k)=f−Ah u(k)
every 10 iterations and at the iteration limit. Its convergence measure is
Rk=‖r(k)‖₂/‖r(0)‖₂. An initially zero residual yields immediate convergence.

The main criterion is Rk≤1e−8. A's accuracy study continues to 1e−10, recording
the first sampled iteration reaching 1e−8 as well. The limit is 100000
iterations; reaching it without meeting the criterion is reported explicitly.
Solve timing includes iteration-time residual checks and in-memory history
updates. Initialization, final error evaluation and file output are excluded.

Planned grid sizes are n=15,31,63. We calculate the interior L∞ error against
the continuous manufactured solution and the observed order log₂(Eh/Eh/2).
These grid spacings halve exactly. Convergence and accuracy reuse the same
runs. Old 2D Laplace cases n=1024/2048 use K=1000 and report R1000.
Their single-run times describe numerical diagnostics, rather than statistical
performance comparisons.

## Local basic-check evidence

Windows, GCC 12.2.0, C++17, -O2, 1 November 2026:

| Case | Observation |
|---|---|
| 3D n=7, K=1000 | R1000=4.393e−16; boundary error=0 |
| Fixed-work solution vs exact discrete solution | Maximum absolute error=2.776e−15 |
| n=7, solve to 1e−10, checks every 10 | Converged at iteration 280; R=7.140e−11 |
| First sampled R≤1e−8 in that solve | Iteration 220 |
| n=7, solve with iteration limit 1 | Correct iteration-limit status; R≈0.6231 |

For the manufactured problem the exact discrete solution is available directly:

\[
\lambda_h=\sum_{d=x,y,z}4h_d^{-2}\sin^2(m_d\pi h_d/2),\quad
(m_x,m_y,m_z)=(1,2,3),\qquad
u_h^*=x+2y+3z+\frac{14\pi^2}{\lambda_h}\prod_d\sin(m_d\pi x_d).
\]

This follows from the sine eigenvalues of the difference operator and its
annihilation of the linear term. The n=7 continuous error is about 0.09445;
this is distinct from error against the discrete solution.

Records: results/final_202611/A_numerics/local_20261101_r2/.
The first runner attempt incorrectly applied the fixed-1000-iteration
grid-error threshold to an early-stopped solve. It now checks the residual
criterion for solve mode. Both attempt directories remain; the solver
required no change.

## Historical serial baseline gap

The controlled Vanda diagnosis used the 2D Laplace problem, n=1024, K=1000,
the same CPU/compiler settings, and eight measured samples per implementation.

| Implementation | Median seconds |
|---|---:|
| Original serial | 3.496400 |
| Iteration-local update maximum | 3.469020 |
| Row-local update maximum | 1.723135 |
| Single-rank MPI sendrecv | 1.746897 |

The row-local variant accumulates each row maximum in a register and combines
row maxima afterwards. The original and iteration-local variants access the
maximum-update value on the stack in the point loop. Controlled source changes,
machine code and timings support code generation for this reduction as the
main source of the approximately twofold difference in this environment.
None of the four update loops was automatically vectorized. Changing g++
to the mpicxx compiler driver alone did not remove the gap.

The mathematical updates and numerical rules were unchanged. The corrected
row-local baseline is close to MPI P1, so the former single-rank advantage
should not be interpreted as multi-process speedup. Historical measurements
retain their original baselines. New scaling uses matching baselines within
each experiment.

Sources:
[row-reduction diagnosis](../evidence/vanda_1499842_local_reduction/analysis.md),
[compiler-driver diagnosis](../evidence/vanda_1499802_single_rank/analysis.md),
[A/B summary](AB_RESULTS_SUMMARY.md).

## Planned cluster result insertion

The n=15/31/63 convergence and precision tables will be generated from
summary.csv and precision.csv. Old 2D R1000 values come from the
laplace2d_legacy rows. Formal Atlas/Vanda data remain pending; the local smoke
outputs above are labelled separately.

AI usage: ChatGPT/Codex assisted with serial implementation, local basic checks,
run/analysis scripts and drafting this section. Members remain responsible
for understanding and reporting their assigned work.

