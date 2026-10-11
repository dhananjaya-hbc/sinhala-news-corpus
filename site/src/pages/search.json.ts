// Static endpoint: the recent headlines for client-side search (search/).
import { data } from "../lib/data";

export function GET() {
  return new Response(JSON.stringify(data.headlines), {
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
