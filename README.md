# Facebook AI Member Management System

Automated workflow orchestration system integrating Facebook Messenger, AI classification, and Google Sheets for member management in a student IT organization.

## Overview

This system automatically:

- Receives messages from a Facebook Page
- Classifies member requests using AI (training leave, meeting leave, pause membership, quit membership)
- Updates member data in Google Sheets
- Sends automated confirmation responses in Vietnamese

## Features

- **Facebook Messenger Integration**: OAuth 2.0 authentication, webhook verification, automated responses
- **AI Classification**: Natural language processing for Vietnamese messages with 90% accuracy target
- **Google Sheets Management**: Automated data updates, fee calculation, dashboard statistics
- **Error Handling**: Comprehensive retry logic, manual review queue for failed operations
- **Observability**: Structured JSON logging, error tracking, performance monitoring

## Prerequisites

- Node.js 18+ and npm
- Facebook Page with Messenger API access
- Google Cloud project with Sheets API enabled
- AI service API key (OpenAI, Anthropic, or custom)

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd facebook-ai-member-management
```

2. Install dependencies:

```bash
npm install
```

3. Configure environment variables:

```bash
cp .env.example .env
# Edit .env with your credentials
```

4. Build the project:

```bash
npm run build
```

## Configuration

See `.env.example` for all required environment variables:

- **Facebook**: App secret, access token, page ID, verify token
- **Google Sheets**: Service account credentials, spreadsheet ID
- **AI Service**: Provider, API key, model, endpoint
- **Application**: Port, environment, log level, timezone

## Usage

### Development

```bash
npm run dev
```

### Production

```bash
npm run build
npm start
```

### Testing

```bash
npm test
npm run test:watch
```

### Linting and Formatting

```bash
npm run lint
npm run format
```

## Project Structure

```
.
├── src/
│   ├── components/       # Core components (FacebookReceiver, AIClassifier, etc.)
│   ├── utils/           # Utility functions (logger, retry, etc.)
│   ├── types/           # TypeScript type definitions
│   └── index.ts         # Main entry point
├── tests/               # Test files
├── dist/                # Compiled JavaScript (generated)
└── .env                 # Environment variables (not in git)
```

## Architecture

The system follows a pipeline architecture:

1. **Facebook_Receiver**: Receives and validates webhook messages
2. **AI_Classifier**: Classifies messages and extracts information
3. **Sheet_Manager**: Updates Google Sheets with member data
4. **Response_Handler**: Sends automated responses to members

Failed operations are recorded in a Manual_Review queue for administrator attention.

## Google Sheets Structure

The system manages five sheets:

- **Members**: Member profiles with status and fee information
- **Leaves**: Training and meeting leave requests
- **Request_History**: Complete audit log of all requests
- **Manual_Review**: Queue for messages requiring manual classification
- **Dashboard**: Real-time statistics and revenue tracking

## License

MIT
