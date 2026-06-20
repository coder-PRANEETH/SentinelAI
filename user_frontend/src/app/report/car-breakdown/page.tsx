import { Suspense } from "react";
import { CarBreakdownForm } from "./CarBreakdownForm";

export default function CarBreakdownPage() {
  return (
    <Suspense fallback={null}>
      <CarBreakdownForm />
    </Suspense>
  );
}
