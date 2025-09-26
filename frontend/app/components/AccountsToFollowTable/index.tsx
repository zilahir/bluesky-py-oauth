import type { CampaignFollowers } from "~/types/Campaigns";
import type { ColumnDef } from "@tanstack/react-table";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableCell,
  TableBody,
} from "../ui/table";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";

type AccountToFollow = CampaignFollowers;

interface IAccountsToFollowTable {
  data: AccountToFollow[];
}

const columns: ColumnDef<AccountToFollow>[] = [
  {
    accessorKey: "account_handle",
    header: "Account Handle",
  },
  {
    accessorKey: "me_following",
    header: "Am I Currently Following?",
    cell: ({ row }) => (row.getValue("me_following") ? "Yes" : "No"),
  },
  {
    accessorKey: "is_following_me",
    header: "Is Following Me",
    cell: ({ row }) => (row.getValue("is_following_me") ? "Yes" : "No"),
  },
];

function AccountsToFollowTable({ data }: IAccountsToFollowTable) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });
  return (
    <div>
      <div className="overflow-hidden rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  return (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext(),
                          )}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

export default AccountsToFollowTable;
