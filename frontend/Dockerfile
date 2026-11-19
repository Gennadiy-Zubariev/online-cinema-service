# Dev image: Vite dev server with hot reload (code comes through a volume).
# A production image (build + nginx) comes with the deploy, block 8.
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
