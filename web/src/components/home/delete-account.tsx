"use client";

import { deleteAccount } from "@/lib/actions";

export function DeleteAccount() {
  return (
    <form
      action={deleteAccount}
      onSubmit={(e) => {
        if (
          !confirm(
            "Delete your account, your history and your data in every room? This can't be undone.",
          )
        ) {
          e.preventDefault();
        }
      }}
    >
      <button type="submit" className="text-danger text-sm font-semibold underline">
        Delete my account
      </button>
    </form>
  );
}
