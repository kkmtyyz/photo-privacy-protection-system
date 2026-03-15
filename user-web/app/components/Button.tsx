import type { ButtonHTMLAttributes } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement>;

export function Button({ children, className = "", ...props }: ButtonProps) {
    return (
      <button
        {...props}
        className={`
          rounded-md border border-gray-400 px-4 py-2
          text-gray-600
          dark:text-white
          transition
          hover:border-green-500 hover:text-green-600
          focus:outline-none focus:ring-2 focus:ring-green-500
          ${className}
        `}
      >
        {children}
      </button>
    );
}

