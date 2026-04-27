#!/bin/bash
# Database Setup Script for Nestle Agentic System

set -e  # Exit on error

echo "================================================"
echo "Nestle Agentic Database Setup"
echo "================================================"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

echo -e "${YELLOW}Database Configuration:${NC}"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  User: $DB_USER"
echo "  Database: $DB_NAME"
echo ""

# Step 1: Check PostgreSQL connection
echo -e "${YELLOW}Step 1: Checking PostgreSQL connection...${NC}"
if pg_isready -h "$DB_HOST" -p "$DB_PORT" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL is running${NC}"
else
    echo -e "${RED}✗ PostgreSQL is not running. Please start PostgreSQL first.${NC}"
    exit 1
fi

# Step 2: Check if we need to configure pg_hba.conf
echo -e "${YELLOW}Step 2: Checking PostgreSQL authentication...${NC}"
if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d postgres -c '\q' > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Password authentication is working${NC}"
else
    echo -e "${YELLOW}⚠ Password authentication is not configured${NC}"
    echo ""
    echo "PostgreSQL needs to be configured for password authentication."
    echo "Please update your pg_hba.conf file (usually at /etc/postgresql/*/main/pg_hba.conf)"
    echo ""
    echo "Change this line:"
    echo "  local   all             all                                     peer"
    echo "  host    all             all             127.0.0.1/32            ident"
    echo ""
    echo "To:"
    echo "  local   all             all                                     md5"
    echo "  host    all             all             127.0.0.1/32            md5"
    echo ""
    echo "Then restart PostgreSQL:"
    echo "  sudo systemctl restart postgresql"
    echo ""
    exit 1
fi

# Step 3: Check if database exists, create if not
echo -e "${YELLOW}Step 3: Checking if database exists...${NC}"
if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
    echo -e "${GREEN}✓ Database '$DB_NAME' already exists${NC}"
else
    echo -e "${YELLOW}Creating database '$DB_NAME'...${NC}"
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME;"
    echo -e "${GREEN}✓ Database '$DB_NAME' created${NC}"
fi

# Step 4: Run Alembic migrations
echo -e "${YELLOW}Step 4: Running Alembic migrations...${NC}"
if command -v conda &> /dev/null && conda env list | grep -q nestle; then
    echo "Using conda environment 'nestle'..."
    conda run -n nestle alembic upgrade head
else
    echo "Running alembic directly..."
    alembic upgrade head
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Alembic migrations completed${NC}"
else
    echo -e "${RED}✗ Alembic migrations failed${NC}"
    echo "Falling back to manual SQL execution..."
fi

# Step 5: Run additional migrations
echo -e "${YELLOW}Step 5: Running additional migrations...${NC}"

# Check if generic_documents table exists
if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='generic_documents'" | grep -q 1; then
    echo -e "${GREEN}✓ generic_documents table already exists${NC}"
else
    echo "Creating generic_documents table..."
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -f migrations/add_generic_documents_table.sql
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ generic_documents table created${NC}"
    else
        echo -e "${RED}✗ Failed to create generic_documents table${NC}"
        exit 1
    fi
fi

# Step 6: Verify tables
echo -e "${YELLOW}Step 6: Verifying database tables...${NC}"
TABLES=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
echo -e "${GREEN}✓ Found $TABLES tables in database${NC}"

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Database setup completed successfully!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "You can now run the application:"
echo "  Backend: conda run -n nestle uvicorn src.main:app --reload"
echo "  Frontend: cd src/ui && npm run dev"
