'use client';
import { useState } from 'react';

export default function SearchBox() {
  const [q, setQ] = useState('');
  const [results, setResults] = useState<{ id: string; name: string }[]>([]);

  async function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    setQ(e.target.value);
    const res = await fetch(`/api/search?q=${encodeURIComponent(e.target.value)}`);
    setResults(await res.json());
  }

  return (
    <div>
      <input value={q} onChange={onChange} placeholder="Search products" />
      <ul>{results.map((r) => <li key={r.id}>{r.name}</li>)}</ul>
    </div>
  );
}
