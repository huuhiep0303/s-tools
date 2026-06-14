# Stage 1: Build the React frontend using the latest Node 22
FROM node:22-alpine AS builder

WORKDIR /app/frontend

# Copy frontend configuration files
COPY frontend/package*.json ./

# Install dependencies (clean install)
RUN npm ci

# Copy the rest of the frontend code and build
COPY frontend/ ./
RUN npm run build

# Stage 2: Serve with FastAPI
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY . .

# Copy the built frontend from the builder stage
COPY --from=builder /app/frontend/dist ./frontend/dist

# Expose port and run the application
# Railway automatically sets the PORT environment variable
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
