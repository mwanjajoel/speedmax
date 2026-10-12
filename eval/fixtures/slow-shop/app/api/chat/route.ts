import Anthropic from '@anthropic-ai/sdk';
import { db } from '../../../lib/db';

const client = new Anthropic();

export async function POST(req: Request) {
  const { question } = await req.json();
  const orders = await db.order.findMany();

  const message = await client.messages.create({
    model: 'claude-sonnet-5-5',
    max_tokens: 2048,
    messages: [{ role: 'user', content: `${question}\n\nOrders:\n${JSON.stringify(orders)}` }],
  });

  const text = message.content.map((b) => (b.type === 'text' ? b.text : '')).join('');
  return Response.json({ text });
}
