# StockPilot WMS - Multi-Tenant SaaS Warehouse Management System

## Overview
StockPilot WMS is a modern, responsive, multi-tenant SaaS Warehouse Management System designed for distributors, wholesalers, e-commerce businesses, retailers, and logistics companies.

## Technology Stack
- **Frontend**: React + TypeScript + Tailwind CSS + shadcn/ui
- **Backend**: FastAPI + Python
- **Database**: MongoDB (with explicit transaction safeguards for inventory consistency)
- **Authentication**: JWT-based
- **PWA**: Service Worker + Web App Manifest
- **Cache/Background**: Redis (optional)

## Project Structure
- `/backend` - FastAPI backend API
- `/frontend` - React frontend application
- `/tests` - Automated tests
- `/docker` - Docker configuration

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- MongoDB 6+
- Redis (optional)

### Development

1. Backend setup:
```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --reload
```

2. Frontend setup:
```bash
cd frontend
npm install
npm start
```

## Environment Variables
See `.env.example` files in backend and frontend directories.