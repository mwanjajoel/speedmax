'use client';
import { useEffect, useState } from 'react';

type Order = { id: string; total: number; customer: { name: string } };

export default function OrderList() {
  const [orders, setOrders] = useState<Order[] | null>(null);

  useEffect(() => {
    fetch('/api/orders?userId=me').then((r) => r.json()).then(setOrders);
  }, []);

  if (!orders) return null;

  return (
    <ul>
      {orders.map((o) => (
        <li key={o.id}>{o.customer.name}: ${o.total / 100}</li>
      ))}
    </ul>
  );
}
