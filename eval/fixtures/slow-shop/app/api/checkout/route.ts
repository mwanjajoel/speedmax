import sharp from 'sharp';
import { db } from '../../../lib/db';
import { sendReceipt } from '../../../lib/mail';

export async function POST(req: Request) {
  const { customerId, total, email } = await req.json();
  const order = await db.order.create({ data: { customerId, userId: customerId, total, status: 'paid' } });

  const receiptImage = await sharp({ create: { width: 2400, height: 3200, channels: 3, background: '#fff' } }).png().toBuffer();
  await sendReceipt(email, `<p>Thanks for order ${order.id}</p>`, receiptImage);

  return Response.json({ id: order.id });
}
