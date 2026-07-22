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
      className={`relative flex items-center bg-white border border-gray-200 shadow-sm hover:border-blue-300 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/10 focus-within:shadow-md transition-all duration-200 ${
        isLg ? "rounded-2xl py-0.5" : "rounded-xl"
      }`}
    >
      <Search
        className={`absolute text-gray-400 pointer-events-none flex-shrink-0 ${
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
          isLg ? "pl-12 pr-4 py-3.5 text-base" : "pl-9 pr-3 py-2 text-sm"
        }`}
      />
      {value && (
        <button
          onClick={handleClear}
          aria-label="清除搜索"
          className="flex-shrink-0 mr-1 p-1.5 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
        >
          <X className={isLg ? "w-4 h-4" : "w-3.5 h-3.5"} />
        </button>
      )}
      <button
        onClick={() => onSearch(value.trim())}
        disabled={!value.trim()}
        className={`flex-shrink-0 mr-1.5 font-semibold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:shadow-md hover:shadow-blue-500/25 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-200 ${
          isLg ? "px-5 py-2 text-sm rounded-xl" : "px-3 py-1.5 text-xs rounded-lg"
        }`}
      >
        搜索
      </button>
    </div>
  );
}
