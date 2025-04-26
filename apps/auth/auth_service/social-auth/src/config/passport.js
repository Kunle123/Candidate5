const passport = require('passport');
const GoogleStrategy = require('passport-google-oauth20').Strategy;
const LinkedInStrategy = require('passport-linkedin-oauth2').Strategy;
const MicrosoftStrategy = require('passport-microsoft').Strategy;

// Serialize user for the session
passport.serializeUser((user, done) => {
  done(null, user);
});

// Deserialize user from the session
passport.deserializeUser((user, done) => {
  done(null, user);
});

// Google Strategy
passport.use(new GoogleStrategy({
    clientID: process.env.GOOGLE_CLIENT_ID,
    clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    callbackURL: "/auth/google/callback",
    passReqToCallback: true
  },
  async (req, accessToken, refreshToken, profile, done) => {
    try {
      // Here you would typically:
      // 1. Check if user exists in your database
      // 2. Create new user if they don't exist
      // 3. Return user object
      
      const user = {
        id: profile.id,
        email: profile.emails[0].value,
        name: profile.displayName,
        provider: 'google',
        accessToken
      };
      
      return done(null, user);
    } catch (error) {
      return done(error, null);
    }
  }
));

// LinkedIn Strategy
passport.use(new LinkedInStrategy({
    clientID: process.env.LINKEDIN_CLIENT_ID,
    clientSecret: process.env.LINKEDIN_CLIENT_SECRET,
    callbackURL: "/auth/linkedin/callback",
    scope: ['r_emailaddress', 'r_liteprofile'],
    passReqToCallback: true
  },
  async (req, accessToken, refreshToken, profile, done) => {
    try {
      const user = {
        id: profile.id,
        email: profile.emails[0].value,
        name: profile.displayName,
        provider: 'linkedin',
        accessToken
      };
      
      return done(null, user);
    } catch (error) {
      return done(error, null);
    }
  }
));
