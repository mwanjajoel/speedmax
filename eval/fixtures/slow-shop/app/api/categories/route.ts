import { db } from '../../../lib/db';

export const dynamic = 'force-dynamic';

// Categories are edited by admins a few times a year.
export async function GET() {
  const categories = await db.category.findMany({ orderBy: { name: 'asc' } });
  return Response.json(categories);
}
