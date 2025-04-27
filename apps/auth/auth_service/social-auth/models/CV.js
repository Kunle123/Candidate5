const { DataTypes } = require('sequelize');
const sequelize = require('./sequelize');
const User = require('./User');

const CV = sequelize.define('CV', {
  id: {
    type: DataTypes.INTEGER,
    autoIncrement: true,
    primaryKey: true,
  },
  userId: {
    type: DataTypes.INTEGER,
    allowNull: false,
    references: {
      model: User,
      key: 'id',
    },
    onDelete: 'CASCADE',
  },
  title: {
    type: DataTypes.STRING,
    allowNull: false,
  },
  content: {
    type: DataTypes.JSONB,
    allowNull: false,
  },
}, {
  timestamps: true,
});

User.hasMany(CV, { foreignKey: 'userId' });
CV.belongsTo(User, { foreignKey: 'userId' });

module.exports = CV; 