/**
 * A non-2xx answer from the API. Carries the status so a caller can tell "the API says this does not exist" (404)
 * from "the API could not answer" (5xx) -- a network failure is a plain TypeError from fetch, not one of these.
 *
 * Its own module rather than part of `@/lib/api`: tests replace that module wholesale with a mock, and the class
 * must stay real for `instanceof` to work on both sides.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
  }
}
