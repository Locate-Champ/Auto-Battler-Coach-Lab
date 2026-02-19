# Auto?Battler Coach Lab

A research sandbox for deterministic simulation + evaluation + explainable decision support in a hex/grid auto?battler ruleset.

This repo focuses on:
- Fast, deterministic simulation runs for offline experiments
- Dataset generation (snapshot rows, aggregated reports)
- Lightweight evaluators (e.g., tree models) for ?board strength? scoring
- A ?planner + critic? style coach that searches candidate actions and explains recommendations

## Quick start

Run the full stack:

```bash
npm start


Frontend typically opens at http://localhost:5173.

Prerequisites

Python 3.10+

Node.js 18+

Install
pip install -r requirements.txt
cd app/frontend && npm install 
