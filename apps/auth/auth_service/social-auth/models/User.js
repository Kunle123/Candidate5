const crypto = require('crypto');
const bcrypt = require('bcryptjs');
const { DataTypes } = require('sequelize');
const sequelize = require('./sequelize');

const User = sequelize.define('User', {
  email: {
    type: DataTypes.STRING,
    unique: true,
    allowNull: false,
  },
  password: DataTypes.STRING,
  facebook: DataTypes.STRING,
  google: DataTypes.STRING,
  linkedin: DataTypes.STRING,
  tokens: {
    type: DataTypes.JSONB, // Store tokens as JSON
    defaultValue: [],
  },
  profile: {
    type: DataTypes.JSONB, // Store profile as JSON
    defaultValue: {},
  },
  passwordResetToken: {
    type: DataTypes.STRING,
    allowNull: true,
  },
  passwordResetExpires: {
    type: DataTypes.DATE,
    allowNull: true,
  },
  emailVerified: {
    type: DataTypes.BOOLEAN,
    defaultValue: false,
  },
  emailVerificationToken: {
    type: DataTypes.STRING,
    allowNull: true,
  },
  emailVerificationExpires: {
    type: DataTypes.DATE,
    allowNull: true,
  },
}, {
  timestamps: true,
});

// Helper method for password hashing
User.hashPassword = async function(password) {
  return bcrypt.hash(password, 10);
};

// Helper method for validating password
User.prototype.comparePassword = async function(candidatePassword) {
  return bcrypt.compare(candidatePassword, this.password);
};

// Helper method for getting gravatar
User.prototype.gravatar = function(size = 200) {
  if (!this.email) {
    return `https://gravatar.com/avatar/00000000000000000000000000000000?s=${size}&d=retro`;
  }
  const sha256 = crypto.createHash('sha256').update(this.email).digest('hex');
  return `https://gravatar.com/avatar/${sha256}?s=${size}&d=retro`;
};

// Helper methods for token generation
User.generateToken = function() {
  return crypto.randomBytes(32).toString('hex');
};

module.exports = User;
