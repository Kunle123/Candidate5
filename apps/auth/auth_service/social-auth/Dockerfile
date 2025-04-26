FROM node:18

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY . .
RUN ls -l /app/src

EXPOSE 8080

CMD ["node", "app.js"]
