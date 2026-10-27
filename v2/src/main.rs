#[tokio::main(worker_threads = 2)]
async fn main() {
    if tezbar_extension_sdk::serve(find_website_v2::Adapter::default())
        .await
        .is_err()
    {
        eprintln!("Find Website stopped because its connection failed.");
        std::process::exit(1);
    }
}
