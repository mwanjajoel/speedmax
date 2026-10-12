'use client';
import { Bar } from 'react-chartjs-2';
import OrderList from '../../components/OrderList';
import Chat from '../../components/Chat';

export default function Dashboard() {
  return (
    <main>
      <h1>Dashboard</h1>
      <Bar data={{ labels: ['Mon', 'Tue'], datasets: [{ label: 'Sales', data: [3, 5] }] }} />
      <OrderList />
      <Chat />
    </main>
  );
}
