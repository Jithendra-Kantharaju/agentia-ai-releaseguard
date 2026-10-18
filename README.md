# Graph Traversal Maze Solver
### COT 6405 – Introduction to Theory of Algorithms

**Author:** Jithendra Kantharaju  
**USN:** 94901097  

---

## Overview

This project implements a graph-based solver for a directional arrow maze.  
Each grid cell contains either:

- a red or blue directional arrow (e.g., `R-N`, `B-SE`)
- the bullseye `O` located in the bottom-right cell

A valid path must satisfy:

1. Moves must follow the direction shown by the arrow in the current cell.  
2. Each move must land on the opposite color (`R → B → R → ...`).  
3. The path must reach the bullseye.

The maze is converted into a directed graph, and a Breadth-First Search (BFS) is performed to find the minimum-move path.

---

## How to Run

### 1. Solve a maze

```bash
python Project.py tiny.txt
python Project.py small.txt
python Project.py rect.txt
python Project.py large.txt
```

Each run creates:

- `<name>_output.txt` — formatted table of moves  
- `<name>_plain.txt` — raw moves used for verification

---

## Verify Output

Run the validator to check correctness:

```bash
python verifyGraph.py tiny.txt tiny_plain.txt
python verifyGraph.py small.txt small_plain.txt
python verifyGraph.py rect.txt rect_plain.txt
python verifyGraph.py large.txt large_plain.txt
```

Expected result:

```
Path is CORRECT.
```

---

## Runtime Measurement

Benchmark all inputs:

```bash
python times_runs.py
```

This prints the runtime for all datasets (`tiny`, `small`, `rect`, `large`).

---

## Project Structure

```
.
├── Project.py
├── graph_builder.py
├── graph_node.py
├── bfs_solver.py
├── print_path.py
├── verifyGraph.py
├── times_runs.py
│
├── tiny.txt
├── small.txt
├── rect.txt
├── large.txt
│
├── tiny_output.txt
├── tiny_plain.txt
├── small_output.txt
├── small_plain.txt
├── rect_output.txt
├── rect_plain.txt
├── large_output.txt
├── large_plain.txt
│
└── Kantharaju_Project-Report.pdf
```

---

## Algorithm Summary

### Graph Builder

- Scans each arrow cell in its direction.
- Creates edges to:
  - all opposite-colored arrows along the ray
  - the bullseye (if encountered)
- Stores direction and distance (e.g., `3E`, `5SE`).

### BFS Solver

- Performs Breadth-First Search from the starting cell.
- Avoids cycles using a visited set.
- Ensures the path found uses the fewest moves.

---

## Time Complexity

### Graph Construction

```
O(N * max(R, C))
```

### BFS Traversal

```
O(N + E)
```

### Overall Complexity

```
O(N * max(R, C))   # Dominated by graph construction
```

Where:

- `N` = number of grid cells  
- `R` = rows  
- `C` = columns  
- `E` = number of edges in the graph  

---

## Report

The complete project report is included:

- **Kantharaju_Project-Report.pdf**

It contains detailed explanations, complexity analysis, performance results, and required answers.

---

## Status

All test cases have been successfully:

- Solved  
- Verified using `verifyGraph.py`  
- Benchmarked using `times_runs.py`  

This project is complete and ready for submission.

---
