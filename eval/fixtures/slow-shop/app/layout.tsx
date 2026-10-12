import { Chart as ChartJS, ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend } from 'chart.js';
import moment from 'moment';
import './globals.css';

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend);

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@100;200;300;400;500;600;700;800;900&family=Playfair+Display:wght@400;700;900&family=Roboto+Mono:wght@400;700&family=Lobster&display=block" />
        <script src="https://www.googletagmanager.com/gtag/js?id=G-XXXX"></script>
        <script src="https://cdn.segment.com/analytics.js/v1/XXXX/analytics.min.js"></script>
        <script src="https://static.hotjar.com/c/hotjar-XXXX.js"></script>
        <script src="https://widget.intercom.io/widget/XXXX"></script>
        <script src="https://cdn.optimizely.com/js/XXXX.js"></script>
      </head>
      <body>
        <header>Slow Shop · {moment().format('YYYY')}</header>
        {children}
      </body>
    </html>
  );
}
