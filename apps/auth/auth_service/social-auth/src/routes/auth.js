const express = require('express');
const passport = require('passport');
const bcrypt = require('bcryptjs');
const User = require('../../models/User');
const router = express.Router();
const jwt = require('jsonwebtoken');
const crypto = require('crypto');
const { Op } = require('sequelize');

// Google Auth Routes
router.get('/google',
  passport.authenticate('google', { scope: ['profile', 'email'] })
);

router.get('/google/callback',
  passport.authenticate('google', { failureRedirect: '/login' }),
  (req, res) => {
    // Successful authentication
    res.redirect('/dashboard');
  }
);

// LinkedIn Auth Routes
router.get('/linkedin',
  passport.authenticate('linkedin')
);

router.get('/linkedin/callback',
  passport.authenticate('linkedin', { failureRedirect: '/login' }),
  (req, res) => {
    // Successful authentication
    res.redirect('/dashboard');
  }
);

// Microsoft Auth Routes
router.get('/microsoft',
  passport.authenticate('microsoft')
);

router.get('/microsoft/callback',
  passport.authenticate('microsoft', { failureRedirect: '/login' }),
  (req, res) => {
    // Successful authentication
    res.redirect('/dashboard');
  }
);

// Logout Route
router.get('/logout', (req, res) => {
  req.logout();
  res.redirect('/');
});

// Get Current User
router.get('/user', (req, res) => {
  if (req.isAuthenticated()) {
    res.json({ user: req.user });
  } else {
    res.status(401).json({ error: 'Not authenticated' });
  }
});

// Email/Password Registration
router.post('/register', async (req, res) => {
  const { name, email, password } = req.body;
  if (!name || !email || !password) {
    return res.status(400).json({ success: false, message: 'Name, email, and password are required.' });
  }
  try {
    // Check if user already exists
    const userCheck = await User.findOne({ where: { email } });
    if (userCheck) {
      return res.status(409).json({ success: false, message: 'Email already registered.' });
    }
    // Hash password
    const password_hash = await bcrypt.hash(password, 10);
    // Insert user
    const user = await User.create({ name, email, password: password_hash });
    res.json({ success: true, message: 'User registered successfully.', user });
  } catch (err) {
    console.error('Registration error:', err);
    res.status(500).json({ success: false, message: 'Registration failed.' });
  }
});

// JWT authentication middleware
function authenticateJWT(req, res, next) {
  const authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith('Bearer ')) {
    const token = authHeader.split(' ')[1];
    // Log the token (first and last 10 chars)
    console.log('About to verify JWT:', token ? token.slice(0, 10) + '...' + token.slice(-10) : 'undefined');
    console.log('DEBUG: Verifying JWT with secret:', process.env.JWT_SECRET);
    jwt.verify(token, process.env.JWT_SECRET, (err, user) => {
      console.log('JWT verify callback triggered. err:', err, 'user:', user);
      if (err) {
        console.error('JWT verification error:', err && err.message, err);
        return res.status(403).json({ success: false, message: 'Invalid token' });
      }
      req.user = user;
      next();
    });
  } else {
    res.status(401).json({ success: false, message: 'No token provided' });
  }
}

// Email/Password Login
router.post('/login', async (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) {
    return res.status(400).json({ success: false, message: 'Email and password are required.' });
  }
  try {
    // Find user
    const user = await User.findOne({ where: { email } });
    if (!user) {
      return res.status(401).json({ success: false, message: 'Invalid email or password.' });
    }
    // Check password
    const valid = await bcrypt.compare(password, user.password);
    if (!valid) {
      return res.status(401).json({ success: false, message: 'Invalid email or password.' });
    }
    // DEBUG: Log JWT_SECRET before signing
    console.log('DEBUG: Signing JWT with secret:', process.env.JWT_SECRET);
    // Issue JWT
    const token = jwt.sign(
      { id: user.id, name: user.name, email: user.email },
      process.env.JWT_SECRET,
      { algorithm: process.env.JWT_ALGORITHM || 'HS256', expiresIn: process.env.JWT_EXPIRATION || '30m' }
    );
    // Return user info and token
    res.json({ success: true, message: 'Login successful.', token, user: { id: user.id, name: user.name, email: user.email } });
  } catch (err) {
    console.error('Login error:', err);
    res.status(500).json({ success: false, message: 'Login failed.' });
  }
});

// Profile endpoint (JWT protected)
router.get('/profile', authenticateJWT, (req, res) => {
  const { id, name, email } = req.user;
  res.json({ success: true, user: { id, name, email } });
});

// Password Reset Request
router.post('/forgot', async (req, res) => {
  const { email } = req.body;
  if (!email) {
    return res.status(400).json({ success: false, message: 'Email is required.' });
  }
  try {
    const user = await User.findOne({ where: { email } });
    if (!user) {
      // For security, do not reveal if the email is not registered
      return res.json({ success: true, message: 'If that email is registered, a reset link has been sent.' });
    }
    const token = crypto.randomBytes(32).toString('hex');
    user.passwordResetToken = token;
    user.passwordResetExpires = new Date(Date.now() + 3600000); // 1 hour
    await user.save();
    // TODO: Send email with reset link (for now, return token in response)
    res.json({ success: true, message: 'Password reset token generated.', token });
  } catch (err) {
    console.error('Forgot password error:', err);
    res.status(500).json({ success: false, message: 'Failed to process password reset request.' });
  }
});

// Password Reset
router.post('/reset', async (req, res) => {
  const { token, password } = req.body;
  if (!token || !password) {
    return res.status(400).json({ success: false, message: 'Token and new password are required.' });
  }
  try {
    const user = await User.findOne({ where: {
      passwordResetToken: token,
      passwordResetExpires: { [Op.gt]: new Date() }
    }});
    if (!user) {
      return res.status(400).json({ success: false, message: 'Invalid or expired token.' });
    }
    user.password = await bcrypt.hash(password, 10);
    user.passwordResetToken = null;
    user.passwordResetExpires = null;
    await user.save();
    res.json({ success: true, message: 'Password has been reset.' });
  } catch (err) {
    console.error('Reset password error:', err);
    res.status(500).json({ success: false, message: 'Failed to reset password.' });
  }
});

// Request Email Verification
router.post('/request-verification', async (req, res) => {
  const { email } = req.body;
  if (!email) {
    return res.status(400).json({ success: false, message: 'Email is required.' });
  }
  try {
    const user = await User.findOne({ where: { email } });
    if (!user) {
      return res.status(404).json({ success: false, message: 'User not found.' });
    }
    const token = crypto.randomBytes(32).toString('hex');
    user.emailVerificationToken = token;
    user.emailVerificationExpires = new Date(Date.now() + 3600000); // 1 hour
    await user.save();
    // TODO: Send email with verification link (for now, return token in response)
    res.json({ success: true, message: 'Verification token generated.', token });
  } catch (err) {
    console.error('Request verification error:', err);
    res.status(500).json({ success: false, message: 'Failed to process verification request.' });
  }
});

// Verify Email
router.post('/verify', async (req, res) => {
  const { token } = req.body;
  if (!token) {
    return res.status(400).json({ success: false, message: 'Verification token is required.' });
  }
  try {
    const user = await User.findOne({ where: {
      emailVerificationToken: token,
      emailVerificationExpires: { [Op.gt]: new Date() }
    }});
    if (!user) {
      return res.status(400).json({ success: false, message: 'Invalid or expired verification token.' });
    }
    user.emailVerified = true;
    user.emailVerificationToken = null;
    user.emailVerificationExpires = null;
    await user.save();
    res.json({ success: true, message: 'Email has been verified.' });
  } catch (err) {
    console.error('Email verification error:', err);
    res.status(500).json({ success: false, message: 'Failed to verify email.' });
  }
});

// Change Password (JWT protected)
router.post('/change-password', authenticateJWT, async (req, res) => {
  const { oldPassword, newPassword } = req.body;
  if (!oldPassword || !newPassword) {
    return res.status(400).json({ success: false, message: 'Old and new passwords are required.' });
  }
  try {
    const user = await User.findOne({ where: { id: req.user.id } });
    if (!user) {
      return res.status(404).json({ success: false, message: 'User not found.' });
    }
    const valid = await bcrypt.compare(oldPassword, user.password);
    if (!valid) {
      return res.status(401).json({ success: false, message: 'Old password is incorrect.' });
    }
    user.password = await bcrypt.hash(newPassword, 10);
    await user.save();
    res.json({ success: true, message: 'Password changed successfully.' });
  } catch (err) {
    console.error('Change password error:', err);
    res.status(500).json({ success: false, message: 'Failed to change password.' });
  }
});

module.exports = router; 