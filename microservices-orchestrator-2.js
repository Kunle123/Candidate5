const { createClient } = require('redis');

const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';
const CHANNEL = process.env.CURSOR_CHANNEL || 'cursor-messages';
const SERVICE = 'microservices';

const client = createClient({ url: REDIS_URL });
const subscriber = client.duplicate();

async function main() {
  await client.connect();
  await subscriber.connect();

  await subscriber.subscribe(CHANNEL, async (message) => {
    console.log(`[${CHANNEL}] Received:`, message);
    let data;
    let isJson = false;
    try {
      data = JSON.parse(message);
      isJson = true;
    } catch (e) {
      data = { text: message };
    }
    // Determine if the message is for this service
    const addressedToService =
      (isJson && (data.service === SERVICE || data.service === 'all')) ||
      (!isJson && (data.text || '').toLowerCase().includes(SERVICE));
    if (!addressedToService) return;
    // Handle explicit JSON actions
    if (isJson && data.action) {
      if (data.action === 'status') {
        // Simulate checking the Microservices status
        const response = {
          service: SERVICE,
          action: 'status-result',
          status: 'All microservices are healthy! 🚦',
          timestamp: new Date().toISOString()
        };
        await client.publish(CHANNEL, JSON.stringify(response));
        return;
      }
    }
    // Robustly extract text for conversational messages
    let text = '';
    if (isJson && typeof message === 'string') {
      text = message.toLowerCase();
    } else if (data.text) {
      text = data.text.toLowerCase();
    } else {
      text = String(message).toLowerCase();
    }
    if (text.includes('status') || text.includes('are microservices healthy')) {
      const response = {
        service: SERVICE,
        action: 'status-result',
        status: 'All microservices are healthy! 🚦',
        conversational: true,
        timestamp: new Date().toISOString()
      };
      await client.publish(CHANNEL, JSON.stringify(response));
      return;
    }
    // Fallback conversational response
    await client.publish(CHANNEL, JSON.stringify({
      service: SERVICE,
      action: 'conversational-response',
      message: `Hi! I received your message: "${text}". How can I help you with the microservices?`,
      timestamp: new Date().toISOString()
    }));
  });

  process.stdin.on('data', async (data) => {
    const msg = data.toString().trim();
    if (msg) {
      await client.publish(CHANNEL, msg);
      console.log(`[${CHANNEL}] Sent:`, msg);
    }
  });

  console.log(`Microservices orchestrator listening on channel "${CHANNEL}". Type a message and press Enter to send.`);
}

main().catch(console.error); 