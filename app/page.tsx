import Picker from "./picker";
import data from "../public/data/restaurants.json";

export default function Home() {
  return <Picker data={data} />;
}
