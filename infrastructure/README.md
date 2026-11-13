# Infrastructure

Day 1 provides local PostgreSQL and FastAPI through the root Docker Compose file.
Both published ports bind to localhost. PostgreSQL data and private invoice files
use named volumes. Run migrations explicitly before seeding or using the API.

Public hosting, a read-only portfolio mode, and VM HTTPS guidance belong to the
deployment milestone. Nothing in this repository has been deployed publicly.
