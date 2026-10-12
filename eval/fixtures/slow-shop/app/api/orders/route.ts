import { db } from '../../../lib/db';

export async function GET(req: Request) {
  const userId = new URL(req.url).searchParams.get('userId')!;
  const orders = await db.order.findMany({ where: { userId, status: { not: 'cancelled' } }, orderBy: { createdAt: 'desc' } });

  const withCustomers = [];
  for (const order of orders) {
    const customer = await db.customer.findUnique({ where: { id: order.customerId } });
    withCustomers.push({ ...order, customer });
  }

  return Response.json(withCustomers);
}
