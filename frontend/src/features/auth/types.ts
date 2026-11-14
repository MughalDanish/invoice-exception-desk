export type AuthUser = {
  id: string;
  username: string;
  role: "OPERATOR";
  session_id: string;
};
export type LoginFields = { username: string; password: string };
