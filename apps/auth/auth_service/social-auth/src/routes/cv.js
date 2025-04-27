const express = require('express');
const router = express.Router();
const CV = require('../../models/CV');
const { Op } = require('sequelize');
const authenticateJWT = require('./auth').authenticateJWT;

// Create a new CV
router.post('/', authenticateJWT, async (req, res) => {
  const { title, content } = req.body;
  if (!title || !content) {
    return res.status(400).json({ success: false, message: 'Title and content are required.' });
  }
  try {
    const cv = await CV.create({
      userId: req.user.id,
      title,
      content,
    });
    res.json({ success: true, message: 'CV created.', cv });
  } catch (err) {
    console.error('Create CV error:', err);
    res.status(500).json({ success: false, message: 'Failed to create CV.' });
  }
});

// List all CVs for the authenticated user
router.get('/', authenticateJWT, async (req, res) => {
  try {
    const cvs = await CV.findAll({ where: { userId: req.user.id } });
    res.json({ success: true, cvs });
  } catch (err) {
    console.error('List CVs error:', err);
    res.status(500).json({ success: false, message: 'Failed to list CVs.' });
  }
});

// Get a specific CV (must own it)
router.get('/:id', authenticateJWT, async (req, res) => {
  try {
    const cv = await CV.findOne({ where: { id: req.params.id, userId: req.user.id } });
    if (!cv) {
      return res.status(404).json({ success: false, message: 'CV not found.' });
    }
    res.json({ success: true, cv });
  } catch (err) {
    console.error('Get CV error:', err);
    res.status(500).json({ success: false, message: 'Failed to get CV.' });
  }
});

// Update a CV (must own it)
router.put('/:id', authenticateJWT, async (req, res) => {
  const { title, content } = req.body;
  try {
    const cv = await CV.findOne({ where: { id: req.params.id, userId: req.user.id } });
    if (!cv) {
      return res.status(404).json({ success: false, message: 'CV not found.' });
    }
    if (title) cv.title = title;
    if (content) cv.content = content;
    await cv.save();
    res.json({ success: true, message: 'CV updated.', cv });
  } catch (err) {
    console.error('Update CV error:', err);
    res.status(500).json({ success: false, message: 'Failed to update CV.' });
  }
});

// Delete a CV (must own it)
router.delete('/:id', authenticateJWT, async (req, res) => {
  try {
    const cv = await CV.findOne({ where: { id: req.params.id, userId: req.user.id } });
    if (!cv) {
      return res.status(404).json({ success: false, message: 'CV not found.' });
    }
    await cv.destroy();
    res.json({ success: true, message: 'CV deleted.' });
  } catch (err) {
    console.error('Delete CV error:', err);
    res.status(500).json({ success: false, message: 'Failed to delete CV.' });
  }
});

module.exports = router; 