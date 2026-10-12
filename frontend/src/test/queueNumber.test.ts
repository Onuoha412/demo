import { formatQueueNumber } from "../utils/queueNumber";

it("formats queue numbers with their prefix and three-digit padding", () => {
  expect(formatQueueNumber("A", 23)).toBe("A023");
  expect(formatQueueNumber("BC", 1000)).toBe("BC1000");
});
