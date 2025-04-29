const { createClient } = require('redis');

const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';
const CHANNEL = process.env.CURSOR_CHANNEL || 'cursor-messages';

const client = createClient({ url: REDIS_URL });
const subscriber = client.duplicate();

async function main() {
  await client.connect();
  await subscriber.connect();

  // Listen for messages
  await subscriber.subscribe(CHANNEL, (message) => {
    console.log(`[${CHANNEL}] Received:`, message);
  });

  // Send a message from stdin
  process.stdin.on('data', async (data) => {
    const msg = data.toString().trim();
    if (msg) {
      await client.publish(CHANNEL, msg);
      console.log(`[${CHANNEL}] Sent:`, msg);
    }
  });

  console.log(`Listening on channel "${CHANNEL}". Type a message and press Enter to send.`);
}

main().catch(console.error); 