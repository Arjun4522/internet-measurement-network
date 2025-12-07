#!/bin/bash
# Complete Docker cleanup and fresh start script for IMN project

echo "========================================"
echo "Docker Complete Cleanup - IMN Project"
echo "========================================"
echo ""

# Step 1: Stop all running containers
echo "Step 1: Stopping all containers..."
docker-compose -f core-pipeline.yml down
echo "✓ Containers stopped"
echo ""

# Step 2: Remove all containers (including stopped ones)
echo "Step 2: Removing all containers..."
docker ps -a --filter "name=internet-measurement-network" --format "{{.ID}}" | xargs -r docker rm -f
docker ps -a --filter "name=server" --format "{{.ID}}" | xargs -r docker rm -f
docker ps -a --filter "name=agent" --format "{{.ID}}" | xargs -r docker rm -f
echo "✓ Containers removed"
echo ""

# Step 3: Remove all images
echo "Step 3: Removing all images..."
docker images --filter "reference=internet-measurement-network*" --format "{{.ID}}" | xargs -r docker rmi -f
echo "✓ Images removed"
echo ""

# Step 4: Remove all volumes
echo "Step 4: Removing all volumes..."
docker volume ls --filter "name=internet-measurement-network" --format "{{.Name}}" | xargs -r docker volume rm -f
docker volume prune -f
echo "✓ Volumes removed"
echo ""

# Step 5: Remove networks
echo "Step 5: Removing networks..."
docker network ls --filter "name=internet-measurement-network" --format "{{.Name}}" | xargs -r docker network rm
docker network ls --filter "name=aiori-net" --format "{{.Name}}" | xargs -r docker network rm
echo "✓ Networks removed"
echo ""

# Step 6: Clean up build cache
echo "Step 6: Cleaning build cache..."
docker builder prune -af
echo "✓ Build cache cleaned"
echo ""

# Step 7: Remove any orphaned resources
echo "Step 7: Removing orphaned resources..."
docker system prune -af --volumes
echo "✓ Orphaned resources removed"
echo ""

# Step 8: Verify cleanup
echo "========================================"
echo "Cleanup Verification"
echo "========================================"
echo ""
echo "Remaining containers:"
docker ps -a | grep -E "(server|agent|internet-measurement)" || echo "  None ✓"
echo ""
echo "Remaining images:"
docker images | grep -E "internet-measurement" || echo "  None ✓"
echo ""
echo "Remaining volumes:"
docker volume ls | grep -E "internet-measurement" || echo "  None ✓"
echo ""
echo "Remaining networks:"
docker network ls | grep -E "(internet-measurement|aiori)" || echo "  None ✓"
echo ""

echo "========================================"
echo "Cleanup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Update your code files (especially clickhouse_manager.py)"
echo "2. Run: docker-compose -f core-pipeline.yml build --no-cache"
echo "3. Run: docker-compose -f core-pipeline.yml up -d"
echo ""