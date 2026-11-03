// Only directory component styles are imported as class maps.
declare module '*/index.less' {
  const classes: Readonly<Record<string, string>>;
  export default classes;
}
