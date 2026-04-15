import { Link } from "react-router-dom";

interface Props {
  billing: { plan: string; plan_name: string };
  status: string;
}

export default function TrialBanner({ billing, status }: Props) {
  if (status !== "trial" && status !== "past_due") return null;

  if (status === "past_due") {
    return (
      <div className="bg-red-50 border-b border-red-200 text-red-800 text-sm py-2 text-center">
        Your last payment failed.{" "}
        <Link to="/app/settings/billing" className="underline">
          Update billing
        </Link>{" "}
        to keep your tenant active.
      </div>
    );
  }

  return (
    <div className="bg-amber-50 border-b border-amber-200 text-amber-900 text-sm py-2 text-center">
      You're on the {billing.plan_name} trial.{" "}
      <Link to="/app/settings/billing" className="underline">
        Upgrade
      </Link>{" "}
      to unlock more OLTs and ONUs.
    </div>
  );
}
