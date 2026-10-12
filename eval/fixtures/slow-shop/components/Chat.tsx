'use client';
import { useState } from 'react';

export default function Chat() {
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);

  async function ask(question: string) {
    setLoading(true);
    const res = await fetch('/api/chat', { method: 'POST', body: JSON.stringify({ question }) });
    const data = await res.json();
    setAnswer(data.text);
    setLoading(false);
  }

  return (
    <div>
      <button onClick={() => ask('Summarize my orders')}>Ask the assistant</button>
      {loading ? <p>Thinking…</p> : <p>{answer}</p>}
    </div>
  );
}
