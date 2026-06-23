'use client';

import { motion } from 'framer-motion';

interface SkeletonProps {
  className?: string;
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
}

export function Skeleton({ className = '', width, height, borderRadius = 8 }: SkeletonProps) {
  return (
    <motion.div
      initial={{ opacity: 0.5 }}
      animate={{ opacity: 1 }}
      transition={{ repeat: Infinity, duration: 1.2, repeatType: "reverse", ease: "easeInOut" }}
      className={`bg-gray-200 dark:bg-gray-800 ${className}`}
      style={{ width, height, borderRadius }}
    />
  );
}
