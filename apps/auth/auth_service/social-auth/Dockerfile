FROM node:20

WORKDIR /app

COPY package*.json ./
RUN yes
npm ci --legacy-peer-deps

COPY . .
RUN ls -l /app/src

EXPOSE 8080

CMD ["npm", "start"]
