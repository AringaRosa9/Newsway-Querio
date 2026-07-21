"use client";

import { useRef, useState, useEffect } from "react";
import { Search, X } from "lucide-react";

interface SearchBoxProps {
  defaultValue?: string;
  size?: "lg" | "sm";
  onSearch: (query: string) => void;
  placeholder?: string;
}

export default function SearchBox({
  defaultValue = "",
  size = "lg",
  onSearch,
  placeholder = "搜索新闻... / Search news...",
}: SearchBoxProps) {
  const [value, setValue] = useState(defaultValue);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync if defaultValue changes (e.g., URL param changes)
  useEffect(() => {
    setValue(defaultValue);
  }, [defaultValue]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      onSearch(value.trim());
    } else if (e.key === "Escape") {
      setValue("");
      inputRef.current?.blur();
    }
  };

  const handleClear = () => {
    setValue("");
    inputRef.current?.focus();
  };

  const isLg = size === "lg";

  return (
    <div
      className={`relative flex items-center bg-white border-2 border-gray-200 rounded-2xl shadow-sm hover:border-blue-400 focus-within:border-blue-500 focus-within:shadow-md transition-all duration-200 ${
        isLg ? "py-1" : ""
      }`}
    >
      <Search
        className={`absolute left-3 text-gray-400 pointer-events-none flex-shrink-0 ${
          isLg ? "w-5 h-5 left-4" : "w-4 h-4 left-3"
        }`}
      />
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={false}
        className={`flex-1 bg-transparent border-none outline-none text-gray-900 placeholder-gray-400 ${
          isLg
            ? "pl-12 pr-4 py-3.5 text-base"
            : "pl-9 pr-3 py-2 text-sm"
        }`}
      />
      {value && (
        <button
          onClick={handleClear}
          aria-label="清除搜索"
          className="flex-shrink-0 mr-1 p-1 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
        >
          <X className={isLg ? "w-4 h-4" : "w-3.5 h-3.5"} />
        </button>
      )}
      <button
        onClick={() => onSearch(value.trim())}
        disabled={!value.trim()}
        className={`flex-shrink-0 mr-2 font-medium text-white bg-blue-600 rounded-xl hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-150 ${
          isLg ? "px-5 py-2 text-sm" : "px-3 py-1.5 text-xs"
        }`}
      >
        搜索
      </button>
    </div>
  );
}
