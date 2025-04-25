# CandidateV Monorepo

This is the monorepo for the CandidateV project, containing both the Next.js frontend and FastAPI backend.

## Project Structure

```
candidatev/
├── apps/
│   ├── frontend/         # Next.js (React + TypeScript)
│   └── backend/          # FastAPI (Python)
├── packages/
│   ├── ui/               # Shared React UI components
│   ├── utils/            # Shared JS/TS utilities
│   └── types/            # Shared TypeScript types
├── .github/
│   └── workflows/        # CI/CD pipelines
├── docker/
│   ├── frontend/         # Dockerfile for frontend
│   └── backend/          # Dockerfile for backend
├── docs/                 # Documentation and diagrams
├── docker-compose.yml    # Orchestrates frontend/backend for local dev
├── README.md
└── .env.example
```

## Getting Started

### 1. Install Dependencies

```bash
yarn install
```

### 2. Run with Docker Compose

```bash
docker-compose up --build
```

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend: [http://localhost:8000](http://localhost:8000)

## Adding More Services
- Add new apps or packages under `apps/` or `packages/` as needed.

## Contributing
- Please see `docs/` for architecture and contribution guidelines. 