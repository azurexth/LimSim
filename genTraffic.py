import itertools

def generate_combinations(numbers):
    combinations = list(itertools.permutations(numbers, 2))
    return combinations

def generate_csv(combinations):
    csv_lines = ["from_id,to_id,direction,demand(veh/h)"]
    for combo in combinations:
        from_id, to_id = combo
        csv_lines.append(f"{from_id},{to_id},1,100")
        csv_lines.append(f"{from_id},{to_id},-1,100")
    return "\n".join(csv_lines)

def main():
    numbers = [0,1,2,3]
    combinations = generate_combinations(numbers)
    csv_content = generate_csv(combinations)
    with open("demands_m510.txt", "w") as file:
        file.write(csv_content)

if __name__ == "__main__":
    main()