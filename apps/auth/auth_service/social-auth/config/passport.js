const crypto = require('crypto');
const passport = require('passport');
const refresh = require('passport-oauth2-refresh');
const { Strategy: LocalStrategy } = require('passport-local');
const { Strategy: FacebookStrategy } = require('passport-facebook');
// const { Strategy: TwitterStrategy } = require('@passport-js/passport-twitter');
// const { Strategy: TwitchStrategy } = require('twitch-passport');
// const { Strategy: GitHubStrategy } = require('passport-github2');
const { OAuth2Strategy: GoogleStrategy } = require('passport-google-oauth');
// const { SteamOpenIdStrategy } = require('passport-steam-openid');
// const { OAuthStrategy } = require('passport-oauth');
const { OAuth2Strategy } = require('passport-oauth');
const OpenIDConnectStrategy = require('passport-openidconnect');
// const { OAuth } = require('oauth');
const moment = require('moment');
const validator = require('validator');

const User = require('../models/User');

// Debug logging for OAuth environment variables
console.log('GOOGLE_CLIENT_ID:', process.env.GOOGLE_CLIENT_ID);
console.log('GOOGLE_CLIENT_SECRET:', process.env.GOOGLE_CLIENT_SECRET);
console.log('LINKEDIN_CLIENT_ID:', process.env.LINKEDIN_CLIENT_ID);
console.log('LINKEDIN_CLIENT_SECRET:', process.env.LINKEDIN_CLIENT_SECRET);
console.log('FACEBOOK_ID:', process.env.FACEBOOK_ID);
console.log('FACEBOOK_SECRET:', process.env.FACEBOOK_SECRET);
console.log('BASE_URL:', process.env.BASE_URL);

passport.serializeUser((user, done) => {
  done(null, user.id);
});

passport.deserializeUser(async (id, done) => {
  try {
    return done(null, await User.findById(id));
  } catch (error) {
    return done(error);
  }
});

function generateState() {
  return crypto.randomBytes(16).toString('hex');
}

/**
 * Sign in using Email and Password.
 */
passport.use(
  new LocalStrategy({ usernameField: 'email' }, (email, password, done) => {
    User.findOne({ email: { $eq: email.toLowerCase() } })
      .then((user) => {
        if (!user) {
          return done(null, false, { msg: `Email ${email} not found.` });
        }
        if (!user.password) {
          return done(null, false, {
            msg: 'Your account was created with a sign-in provider. You can log in using the provider or an email link. To enable email and password login, set a new password in your profile settings.',
          });
        }
        user.comparePassword(password, (err, isMatch) => {
          if (err) {
            return done(err);
          }
          if (isMatch) {
            return done(null, user);
          }
          return done(null, false, { msg: 'Invalid email or password.' });
        });
      })
      .catch((err) => done(err));
  }),
);

/**
 * OAuth Strategy Overview
 *
 * - User is already logged in.
 *   - Check if there is an existing account with a provider id.
 *     - If there is, return an error message. (Account merging not supported)
 *     - Else link new OAuth account with currently logged-in user.
 * - User is not logged in.
 *   - Check if it's a returning user.
 *     - If returning user, sign in and we are done.
 *     - Else check if there is an existing account with user's email.
 *       - If there is, return an error message.
 *       - Else create a new account.
 */

/**
 * Common function to handle OAuth2 token processing and saving user data.
 *
 * This function is to handle various senarious that we would run into when it comes to
 * processing the OAuth2 tokens and saving the user data.
 *
 * If we have an existing tokens:
 *    - Updates the access token
 *    - Updates access token expiration if provided
 *    - Updates refresh token if provided
 *    - Updates refresh token expiration if provided
 *    - Removes expiration dates if new tokens don't have them
 *
 * If no tokens exists:
 *    - Creates new token entry with provided tokens and expirations
 */
async function saveOAuth2UserTokens(req, accessToken, refreshToken, accessTokenExpiration, refreshTokenExpiration, providerName, tokenConfig = {}) {
  try {
    let user = await User.findById(req.user._id);
    if (!user) {
      // If user is not found in DB, use the one from the request because we are creating a new user
      user = req.user;
    }
    const providerToken = user.tokens.find((token) => token.kind === providerName);
    if (providerToken) {
      providerToken.accessToken = accessToken;
      if (accessTokenExpiration) {
        providerToken.accessTokenExpires = moment().add(accessTokenExpiration, 'seconds').format();
      } else {
        delete providerToken.accessTokenExpires;
      }
      if (refreshToken) {
        providerToken.refreshToken = refreshToken;
      }
      if (refreshTokenExpiration) {
        providerToken.refreshTokenExpires = moment().add(refreshTokenExpiration, 'seconds').format();
      } else if (refreshToken) {
        // Only delete refresh token expiration if we got a new refresh token and don't have an expiration for it
        delete providerToken.refreshTokenExpires;
      }
    } else {
      const newToken = {
        kind: providerName,
        accessToken,
        ...(accessTokenExpiration && {
          accessTokenExpires: moment().add(accessTokenExpiration, 'seconds').format(),
        }),
        ...(refreshToken && { refreshToken }),
        ...(refreshTokenExpiration && {
          refreshTokenExpires: moment().add(refreshTokenExpiration, 'seconds').format(),
        }),
      };
      user.tokens.push(newToken);
    }

    if (tokenConfig) {
      Object.assign(user, tokenConfig);
    }

    user.markModified('tokens');
    await user.save();
    return user;
  } catch (err) {
    throw new Error(err);
  }
}

/**
 * Sign in with Facebook.
 */
passport.use(
  new FacebookStrategy(
    {
      clientID: process.env.FACEBOOK_ID,
      clientSecret: process.env.FACEBOOK_SECRET,
      callbackURL: `${process.env.BASE_URL}/auth/facebook/callback`,
      profileFields: ['name', 'email', 'link', 'locale', 'timezone', 'gender'],
      state: generateState(),
      passReqToCallback: true,
    },
    async (req, accessToken, refreshToken, params, profile, done) => {
      // Facebook does not provide a refresh token but includes an expiration for the access token
      try {
        if (req.user) {
          const existingUser = await User.findOne({
            facebook: { $eq: profile.id },
          });
          if (existingUser) {
            req.flash('errors', {
              msg: 'There is another account in our system linked to your Facebook account. Please delete the duplicate account before linking Facebook to your current account.',
            });
            if (req.session) req.session.returnTo = undefined; // Prevent infinite redirect loop
            return done(null, req.user);
          }
          const user = await saveOAuth2UserTokens(req, accessToken, null, params.expires_in, null, 'facebook');
          user.facebook = profile.id;
          user.profile.name = user.profile.name || `${profile.name.givenName} ${profile.name.familyName}`;
          user.profile.gender = user.profile.gender || profile._json.gender;
          user.profile.picture = user.profile.picture || `https://graph.facebook.com/${profile.id}/picture?type=large`;
          await user.save();
          req.flash('info', { msg: 'Facebook account has been linked.' });
          return done(null, user);
        }
        const existingUser = await User.findOne({
          facebook: { $eq: profile.id },
        });
        if (existingUser) {
          return done(null, existingUser);
        }
        const emailFromProvider = profile._json.email;
        const normalizedEmail = emailFromProvider ? validator.normalizeEmail(emailFromProvider, { gmail_remove_dots: false }) : undefined;
        const existingEmailUser = await User.findOne({
          email: { $eq: normalizedEmail },
        });
        if (existingEmailUser) {
          req.flash('errors', {
            msg: `Unable to sign in with Facebook at this time. If you have an existing account in our system, please sign in by email and link your account to Facebook in your user profile settings.`,
          });
          return done(null, false);
        }
        const user = new User();
        user.email = normalizedEmail;
        user.facebook = profile.id;
        req.user = user;
        await saveOAuth2UserTokens(req, accessToken, null, params.expires_in, null, 'facebook');
        user.profile.name = `${profile.name.givenName} ${profile.name.familyName}`;
        user.profile.gender = profile._json.gender;
        user.profile.picture = `https://graph.facebook.com/${profile.id}/picture?type=large`;
        user.profile.location = profile._json.location ? profile._json.location.name : '';
        await user.save();
        return done(null, user);
      } catch (err) {
        return done(err);
      }
    },
  ),
);

/**
 * Sign in with Google.
 */
const googleStrategyConfig = new GoogleStrategy(
  {
    clientID: process.env.GOOGLE_CLIENT_ID,
    clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    callbackURL: '/auth/google/callback',
    scope: ['profile', 'email', 'https://www.googleapis.com/auth/drive.metadata.readonly', 'https://www.googleapis.com/auth/spreadsheets.readonly'],
    accessType: 'offline',
    prompt: 'consent',
    state: generateState(),
    passReqToCallback: true,
  },
  async (req, accessToken, refreshToken, params, profile, done) => {
    try {
      if (req.user) {
        const existingUser = await User.findOne({
          google: { $eq: profile.id },
        });
        if (existingUser) {
          req.flash('errors', {
            msg: 'There is another account in our system linked to your Google account. Please delete the duplicate account before linking Google to your current account.',
          });
          if (req.session) req.session.returnTo = undefined;
          return done(null, req.user);
        }
        const user = await saveOAuth2UserTokens(req, accessToken, refreshToken, params.expires_in, null, 'google');
        user.google = profile.id;
        user.profile.name = user.profile.name || profile.displayName;
        user.profile.gender = user.profile.gender || profile._json.gender;
        user.profile.picture = user.profile.picture || profile._json.picture;
        await user.save();
        req.flash('info', { msg: 'Google account has been linked.' });
        return done(null, user);
      }
      const existingUser = await User.findOne({ google: { $eq: profile.id } });
      if (existingUser) {
        return done(null, existingUser);
      }
      const emailFromProvider = profile.emails && profile.emails[0] && profile.emails[0].value ? profile.emails[0].value : undefined;
      const normalizedEmail = emailFromProvider ? validator.normalizeEmail(emailFromProvider, { gmail_remove_dots: false }) : undefined;
      const existingEmailUser = await User.findOne({
        email: { $eq: normalizedEmail },
      });
      if (existingEmailUser) {
        req.flash('errors', {
          msg: `Unable to sign in with Google at this time. If you have an existing account in our system, please sign in by email and link your account to Google in your user profile settings.`,
        });
        return done(null, false);
      }
      const user = new User();
      user.email = normalizedEmail;
      user.google = profile.id;
      req.user = user; // Set req.user so saveOAuth2UserTokens can use it
      await saveOAuth2UserTokens(req, accessToken, refreshToken, params.expires_in, null, 'google');
      user.profile.name = profile.displayName;
      user.profile.gender = profile._json.gender;
      user.profile.picture = profile._json.picture;
      await user.save();
      return done(null, user);
    } catch (err) {
      return done(err);
    }
  },
);
passport.use('google', googleStrategyConfig);
refresh.use('google', googleStrategyConfig);

/**
 * Sign in with LinkedIn using OpenID Connect.
 */
passport.use(
  'linkedin',
  new OpenIDConnectStrategy(
    {
      issuer: 'https://www.linkedin.com/oauth',
      authorizationURL: 'https://www.linkedin.com/oauth/v2/authorization',
      tokenURL: 'https://www.linkedin.com/oauth/v2/accessToken',
      userInfoURL: 'https://api.linkedin.com/v2/userinfo',
      clientID: process.env.LINKEDIN_CLIENT_ID,
      clientSecret: process.env.LINKEDIN_CLIENT_SECRET,
      callbackURL: `${process.env.BASE_URL}/auth/linkedin/callback`,
      scope: ['openid', 'profile', 'email'],
      passReqToCallback: true,
    },
    async (req, issuer, profile, params, done) => {
      try {
        if (!profile || !profile.id) {
          return done(null, false, {
            message: 'No profile information received.',
          });
        }
        if (req.user) {
          const existingUser = await User.findOne({
            linkedin: { $eq: profile.id },
          });
          if (existingUser) {
            req.flash('errors', {
              msg: 'There is another account in our system linked to your LinkedIn account. Please delete the duplicate account before linking LinkedIn to your current account.',
            });
            if (req.session) req.session.returnTo = undefined;
            return done(null, req.user);
          }
          const user = await User.findById(req.user.id);
          user.linkedin = profile.id;
          user.tokens.push({ kind: 'linkedin', accessToken: null }); // null for now since passport-openidconnect isn't returning it yet; will update when it supports it
          user.profile.name = user.profile.name || profile.displayName;
          user.profile.picture = user.profile.picture || profile.photos;
          await user.save();
          req.flash('info', { msg: 'LinkedIn account has been linked.' });
          return done(null, user);
        }
        const existingUser = await User.findOne({
          linkedin: { $eq: profile.id },
        });
        if (existingUser) {
          return done(null, existingUser);
        }
        const email = profile.emails && profile.emails[0] && profile.emails[0].value ? profile.emails[0].value : undefined;
        const normalizedEmail = email ? validator.normalizeEmail(email, { gmail_remove_dots: false }) : undefined;
        const existingEmailUser = await User.findOne({ email: { $eq: normalizedEmail } });
        if (existingEmailUser) {
          req.flash('errors', {
            msg: `Unable to sign in with LinkedIn at this time. If you have an existing account in our system, please sign in by email and link your account to LinkedIn in your user profile settings.`,
          });
          return done(null, false);
        }
        const user = new User();
        user.linkedin = profile.id;
        user.tokens.push({ kind: 'linkedin', accessToken: null });
        user.email = normalizedEmail;
        user.profile.name = profile.displayName;
        user.profile.picture = profile.photos || '';
        await user.save();
        return done(null, user);
      } catch (err) {
        return done(err);
      }
    },
  ),
);

// Add debug logging for callback URLs
console.log('Google callback URL:', `${process.env.BASE_URL}/auth/google/callback`);
console.log('LinkedIn callback URL:', `${process.env.BASE_URL}/auth/linkedin/callback`);
console.log('Facebook callback URL:', `${process.env.BASE_URL}/auth/facebook/callback`);

/**
 * Login Required middleware.
 */
exports.isAuthenticated = (req, res, next) => {
  if (req.isAuthenticated()) {
    return next();
  }
  req.flash('errors', { msg: 'You need to be logged in to access that page.' });
  res.redirect('/login');
};

/**
 * Authorization Required middleware.
 */
exports.isAuthorized = async (req, res, next) => {
  const provider = req.path.split('/')[2];
  const token = req.user.tokens.find((token) => token.kind === provider);
  if (token) {
    if (token.accessTokenExpires && moment(token.accessTokenExpires).isBefore(moment().subtract(1, 'minutes'))) {
      if (token.refreshToken) {
        if (token.refreshTokenExpires && moment(token.refreshTokenExpires).isBefore(moment().subtract(1, 'minutes'))) {
          return res.redirect(`/auth/${provider}`);
        }
        try {
          const newTokens = await new Promise((resolve, reject) => {
            refresh.requestNewAccessToken(`${provider}`, token.refreshToken, (err, accessToken, refreshToken, params) => {
              if (err) reject(err);
              resolve({ accessToken, refreshToken, params });
            });
          });

          req.user.tokens.forEach((tokenObject) => {
            if (tokenObject.kind === provider) {
              tokenObject.accessToken = newTokens.accessToken;
              if (newTokens.params.expires_in) tokenObject.accessTokenExpires = moment().add(newTokens.params.expires_in, 'seconds').format();
            }
          });

          await req.user.save();
          return next();
        } catch (err) {
          console.log(err);
          return res.redirect(`/auth/${provider}`);
        }
      } else {
        return res.redirect(`/auth/${provider}`);
      }
    } else {
      return next();
    }
  } else {
    return res.redirect(`/auth/${provider}`);
  }
};

// Add export for testing the internal function
exports._saveOAuth2UserTokens = saveOAuth2UserTokens;
