import nodemailer from 'nodemailer';

const transport = nodemailer.createTransport(process.env.SMTP_URL);

export async function sendReceipt(to: string, html: string, attachment: Buffer) {
  await transport.sendMail({ from: 'shop@example.com', to, subject: 'Your receipt', html, attachments: [{ filename: 'receipt.png', content: attachment }] });
}
