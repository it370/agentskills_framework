// Mock API route for resolving errors
// Remove this file when using real backend

import { NextResponse } from 'next/server';

export async function POST(
  request: Request,
  { params }: { params: { id: string } }
) {
  return NextResponse.json({
    status: "success",
    message: `Error ${params.id} marked as resolved (mock)`,
    error_id: parseInt(params.id),
    resolved_by: "mock_admin@example.com"
  });
}
