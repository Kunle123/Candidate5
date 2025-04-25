# Dockerfile for Next.js frontend
FROM node:18
WORKDIR /app
COPY ../../apps/frontend/package.json ./
COPY ../../apps/frontend/yarn.lock ./
RUN yarn install
COPY ../../apps/frontend .
EXPOSE 3000
CMD ["yarn", "dev"] 