/**
 * server.js
 * 
 * Main entry point for the CandidateV Auth Service.
 * 
 * - Sets up Express server with robust CORS handling for production and development.
 * - Configures secure session management with Redis.
 * - Initializes Passport for authentication.
 * - Mounts authentication routes and health check.
 * - Handles errors gracefully.
 * 
 * Created: 2024-04-27
 * Author: CandidateV Team
 */

require('dotenv').config();
const express = require('express');
const session = require('express-session');
const passport = require('passport');
const cors = require('cors');
const morgan = require('morgan');
const RedisStore = require('connect-redis').default;
const { createClient } = require('redis');

// Import routes and passport config
const authRoutes = require('./routes/auth');
require('./config/passport');

const app = express();

// --- CORS Configuration ---
// Allow only trusted origins (add more as needed)
const allowedOrigins = [
  'https://candidate-v-frontend.vercel.app',
  'https://candidate-v.vercel.app',
  'https://candidatev.vercel.app',
  'https://api-gw-production.up.railway.app',
  'http://localhost:3000'
];

app.use(cors({
  origin: function (origin, callback) {
    if (!origin) return callback(null, true);
    if (allowedOrigins.includes(origin)) {
      return callback(null, origin); // Echo the actual origin
    } else {
      console.warn('Blocked by CORS:', origin);
      return callback(null, false); // No CORS headers
    }
  },
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// Manual OPTIONS handler for robust preflight support
app.options('*', cors());

// --- Middleware ---
app.use(morgan('dev'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// --- Session Configuration ---
const redisClient = createClient({ url: process.env.REDIS_URL });
redisClient.connect().catch(console.error);

app.use(session({
  store: new RedisStore({ client: redisClient }),
  secret: process.env.SESSION_SECRET || 'your-secret-key',
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: process.env.NODE_ENV === 'production', // HTTPS only in production
    sameSite: 'none', // Required for cross-site cookies
    maxAge: 24 * 60 * 60 * 1000 // 24 hours
  }
}));

// --- Passport Initialization ---
app.use(passport.initialize());
app.use(passport.session());

// --- Routes ---
app.use('/auth', authRoutes);

// --- Health Check ---
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok', message: 'Auth service is running' });
});

// --- Error Handling ---
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({
    error: 'Internal Server Error',
    message: process.env.NODE_ENV === 'development' ? err.message : 'Something went wrong'
  });
});

// --- Start Server ---
const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Auth service listening on port ${PORT}`);
  console.log(`Environment: ${process.env.NODE_ENV}`);
});

module.exports = app; 